from chalice import Response, Chalice, Blueprint
import hashlib
import pickle
from jinja2 import meta, FileSystemLoader
from chalice_http_toolkit.content import ContentManager
from typing import Optional, Callable, Union
from datetime import datetime
import traceback
import os

class CloudFront:
    """
    Supports caching via CloudFront for the following usecases:
    - Jinja2 Templates by exploring dependancy trees of templates and their arguments.
    - Static content by extracting modified dates from static content.

    :param content_manager: challice_http_toolkit.ContentManager
    :param app: Chalice or Blueprint
    :param default_cache_control: Cache control to use if none specified
    :returns: CloudFront instance
    """
    def __init__(self, content_manager:ContentManager, app:Union[Chalice, Blueprint], default_cache_control='no-cache'):
        self.__fsl = FileSystemLoader(content_manager.templates_dir)
        self.__cm = content_manager
        self.__app = app
        self.__default_cache_control = default_cache_control
        self.__template_cache = {}

    def __template_calculate(self, filename:str, **kwargs) -> str:
        """
        Calculates a SHA1 hash of a template, its dependancies (extends and includes) and arguments
        without rendering it. This value is then partially cached to speed up future calls.

        :param filename: Path to template relative to ContentManager.templates_dir
        :param kwargs: Arguments to pass to template
        :returns: String SHA1
        """
        hsh = hashlib.sha1()
        existing = self.__template_cache.get(filename)
        if existing:
            hsh.update(existing.encode('utf-8'))
            print('Using cached %s' % existing)
        else:
            seen = []
            self.__hash_template(filename, hsh, seen=seen)
            self.__template_cache[filename] = str(hsh.hexdigest())
            hsh = hashlib.sha1()
            hsh.update(self.__template_cache.get(filename).encode('utf-8'))

        print(f'Hashing template arguments')
        hsh.update(pickle.dumps(kwargs))
        return str(hsh.hexdigest())

    def __hash_template(self, filename:str, hsh:hashlib.sha1, seen=None) -> None:
        """
        Recursive function to hash template and its children (extends and includes)

        :param filename: Path to template
        :param hsh: SHA1 hash to update
        :param seen: Templates seen by filename for prevention of circular references
        :returns: None
        """
        if filename in seen:
            return
        seen.append(filename)
        print(f'Hashing {filename}')
        source, filename, uptodate = self.__fsl.get_source(self.__cm.env, filename)
        hsh.update(source.encode('utf-8'))
        for dep in meta.find_referenced_templates(self.__cm.env.parse(source)):
            self.__hash_template(dep, hsh, seen=seen)

    def template(self, filename:str, status_code:int=200, headers:Optional[dict]=None, cache_control:Optional[str]=None, **kwargs) -> Response:
        """
        If CloudFront supplies If-None-Match header in request, then we can check against a hash
        of the template, its dependancies, and its arguments to inform CloudFront if its cache needs
        to be updated or not.

        :param filename: Path to template in which to be rendered or cached
        :param status_code: Status code to return content with
        :param headers: Additional headers to return
        :param cache_control: Controls how CloudFront manages re-evaluating the orgin. See https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html and https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control.
        :param kwargs: Keyword arguments to be passed to template in the event that it is rendered, must be pickleable
        :returns: Chalice Response object
        """
        if headers is None:
            headers = {}
        if self.__app.current_request is None:
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.html(self.__cm.render_template(filename, **kwargs), status_code=status_code, headers=headers)

        if_none_match = self.__app.current_request.headers.get('If-None-Match')
        print(f'If-None-Match: {if_none_match}')
        try:
            print(f'Path: {filename}')
            hsh = self.__template_calculate(filename, **kwargs)
            if isinstance(if_none_match, str) and if_none_match == hsh:
                print(f'If-None-Match: {if_none_match} == {hsh}, Return 304')
                return Response(body='', status_code=304)
            else:
                print(f'If-None-Match: {if_none_match} != {hsh}, Calling origin function')
                r = self.__cm.html(self.__cm.render_template(filename, **kwargs), status_code=status_code, headers=headers)
                r.headers['ETag'] = hsh
                r.headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
                return r
        except Exception as e:
            print('Exception')
            traceback.print_exc()
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.html(self.__cm.render_template(filename, **kwargs), status_code=status_code, headers=headers)

    def static(self, filename:str, status_code:int=200, headers:Optional[dict]=None, cache_control:Optional[str]=None) -> Response:
        """
        If CloudFront supplies If-Modified-Since header in request, then we can check against the
        modified date of the file to inform CloudFront if its cache needs to be updated or not.

        :param filename: Path relative from static_dir to content
        :param status_code: Status code to return content with
        :param headers: Additional headers to return
        :param cache_control: Controls how CloudFront manages re-evaluating the orgin. See https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html and https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control.
        :returns: Chalice Response object
        """
        if headers is None:
            headers = {}
        if self.__app.current_request is None:
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.static(filename, status_code=status_code, headers=headers)

        if_modified_since = self.__app.current_request.headers.get('If-Modified-Since')
        print(f'If-Modified-Since: {if_modified_since}')
        try:
            path = os.path.join(self.__cm.static_dir, filename)
            print(f'Path: {path}')
            mtime = datetime.utcfromtimestamp(os.path.getmtime(path)).replace(microsecond=0)
            if if_modified_since is not None and isinstance(if_modified_since, str):
                if_modified_since = datetime.strptime(if_modified_since, '%a, %d %b %Y %H:%M:%S %Z')

            if if_modified_since is not None and isinstance(if_modified_since, datetime) and mtime <= if_modified_since:
                print(f'If-Modified-Since: {mtime} <= {if_modified_since}, Return 304')
                return Response(body='', status_code=304)
            else:
                print(f'If-Modified-Since: {mtime} > {if_modified_since}, Calling origin function')
                r = self.__cm.static(filename, status_code=status_code, headers=headers)
                r.headers['Last-Modified'] = mtime.strftime('%a, %d %b %Y %H:%M:%S GMT')
                r.headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
                return r
        except Exception as e:
            print('Exception')
            traceback.print_exc()
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.static(filename, status_code=status_code, headers=headers)

    def asset(self, get_asset:Callable[[],bytes], get_etag:Callable[[],str], status_code:int=200, headers:Optional[dict]=None, cache_control:Optional[str]=None) -> Response:
        """
        Calls get_etag() to generate a tag for the asset, and if it matches the If-None-Match value,
        we return a 304. Otherwise get_asset() is called and returned.

        :param get_asset: Callable to get the asset if ETag doesnt match If-None-Match value
        :param get_etag: Callable to get etag of the asset
        :param status_code: Status code to return content with
        :param headers: Additional headers to return
        :param cache_control: Controls how CloudFront manages re-evaluating the orgin. See https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Expiration.html and https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Cache-Control.
        :returns: Chalice Response object
        """
        if headers is None:
            headers = {}
        if self.__app.current_request is None:
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.asset(get_asset(), status_code=status_code, headers=headers)

        if_none_match = self.__app.current_request.headers.get('If-None-Match')
        print(f'If-None-Match: {if_none_match}')
        try:
            hsh = hashlib.sha1()
            hsh.update(get_etag().encode('utf-8'))
            hsh = str(hsh.hexdigest())
            if isinstance(if_none_match, str) and hsh is not None and if_none_match == hsh:
                print(f'If-None-Match: {if_none_match} == {hsh}, Return 304')
                return Response(body='', status_code=304)
            else:
                print(f'If-None-Match: {if_none_match} != {hsh}, Calling origin function')
                r = self.__cm.asset(get_asset(), status_code=status_code, headers=headers)
                r.headers['ETag'] = hsh
                r.headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
                return r
        except Exception as e:
            print('Exception')
            traceback.print_exc()
            headers['Cache-Control'] = cache_control if cache_control is not None else self.__default_cache_control
            return self.__cm.asset(get_asset(), status_code=status_code, headers=headers)
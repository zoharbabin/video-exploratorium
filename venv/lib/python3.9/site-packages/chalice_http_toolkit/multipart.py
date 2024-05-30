from requests_toolbelt import MultipartDecoder
from chalice import Chalice, Blueprint
from typing import Union

def ex_multipart(app:Union[Chalice,Blueprint]) -> dict:
    """
    Decodes content_type='multipart/form-data'  and returns a dictionary of parts in the format:
    {
        "<name>": {"data": <content>, "filename": <filename>}
    }
    :returns: Dictionary of decoded content
    """
    def ex_filename(raw_name):
        for header in raw_name.split(';'):
            if 'filename' in header:
                return header.split('"')[1::2][0]
        raise Exception('Failed to extract filename')
    def ex_name(raw_name):
        for header in raw_name.split(';'):
            if 'name' in header:
                return header.split('"')[1::2][0]
        raise Exception('Failed to extract name')

    parts = {}
    for part in MultipartDecoder(app.current_request.raw_body, app.current_request.headers['content-type']).parts:
        raw_name = str(part.headers[b'Content-Disposition'], 'utf-8')
        name = None
        filename = None
        if "name" in raw_name:
            name = ex_name(raw_name)
        if "filename" in raw_name:
            filename = ex_filename(raw_name)
        if name:
            parts[name] = {'data': part.content, 'filename': filename}
    return parts
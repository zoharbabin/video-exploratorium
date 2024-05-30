#!/usr/bin/env python3

import argparse
import os
import sys
import shutil
from distutils.dir_util import copy_tree
import requests
import json

aws_regions = ['ap-east-1', 'ap-northeast-1', 'ap-northeast-2', 'ap-south-1', 'ap-southeast-1',
               'ap-southeast-2', 'ca-central-1', 'eu-central-1', 'eu-north-1', 'eu-west-1', 'eu-west-2',
               'eu-west-3', 'me-south-1', 'sa-east-1', 'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2']

def get_layers(region):
    layers = [f'jinja2',
              f'Pillow']
    klayers_path = f'https://api.klayers.cloud/api/v2/p{sys.version_info.major}.{sys.version_info.minor}/layers/latest/{region}/csv'

    possibilities = []
    r = requests.get(klayers_path, stream=True)
    for line in r.iter_lines(decode_unicode=True):
        for layer in layers:
            if line.startswith(layer):
                possibilities.append(line)
    
    latest = {}
    for layer in possibilities:
        parts_by_comma = layer.split(',')
        name = parts_by_comma[0]
        arn = parts_by_comma[2]
        latest[name] = arn
    
    return list(latest.values())

def on_layers(a):
    if isinstance(a.region, (list, tuple)):
        a.region = a.region[0]
    layers = get_layers(a.region)
    if not a.json:
        for l in layers:
            print(l)
    else:
        print(json.dumps(layers, indent=2))
    sys.exit(0)

def load_and_replace(path, replacements):
    with open(path, 'r') as f:
        s = f.read()
    for key, value in replacements.items():
        s = s.replace(key, value)
    return s

def on_create(a):
    if isinstance(a.region, (list, tuple)):
        a.region = a.region[0]
    print(f'Setting up in directory: {a.path}')
    directories = ['chalicelib/libs/', 'chalicelib/static/', 'chalicelib/templates/', '.chalice/']
    for d in directories:
        print(f'Making directory {d}')
        p = os.path.join(a.path, d)
        os.makedirs(p, exist_ok=True)

    this_dir = os.path.dirname(os.path.realpath(__file__))
    assets_dir = os.path.join(this_dir, 'assets')
    use_magic = ""
    cm_use_magic = ""
    if a.options is not None:
        if 'magic' in a.options:
            print('Including libmagic in chalicelib/libs/')
            magic_path = os.path.join(a.path, 'chalicelib/libs/')
            copy_tree(os.path.join(assets_dir, 'magic'), magic_path)
            cm_use_magic = ", magic"
            use_magic = f"""
if os.environ.get('STAGE', '') == 'prod' and 'AWS_CHALICE_CLI_MODE' not in os.environ:
    # Running on AWS, need to use bundled version of magic
    magic_file = os.path.join(chalicelib_dir, 'libs', 'sharemagic')
    print('Using magic file: %s' % magic_file)
    magic = Magic(magic_file=magic_file, mime=True)
else:
    # Running locally, use system version of magic
    magic = Magic(mime=True)"""

    print('Writing app.py')
    with open(os.path.join(a.path, 'app.py'), 'w') as f:
        f.write(load_and_replace(os.path.join(assets_dir, 'app.py'),
                                 {'<app_name>': a.name,
                                  '<use_magic>': use_magic,
                                  '<cm_use_magic>': cm_use_magic}))
    
    print('Writing .chalice/config.json')
    with open(os.path.join(a.path, '.chalice/config.json'), 'w') as f:
        layers = get_layers(a.region)
        layers = '"' + '",\n"'.join(layers) + '"'
        f.write(load_and_replace(os.path.join(assets_dir, 'config.json'),
                                 {'<app_name>': a.name,
                                  '<layers>': layers}))

    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(description='chalice-http-toolkit project management script')
    subparsers = parser.add_subparsers()

    parser_create = subparsers.add_parser('setup', help='Sets up a new chalice-http-toolkit project')
    parser_create.add_argument('-n', dest='name', type=str, help='Name of application', required=True)
    parser_create.add_argument('-p', dest='path', type=str, help='Path where project should be created', required=True)
    parser_create.add_argument('-e', dest='options', type=str, help='Enable multiple different optional features', required=False, choices=['magic'])
    parser_create.add_argument('-r', dest='region', type=str, help='AWS Region', required=False, default='us-east-1', nargs=1, choices=aws_regions)
    parser_create.set_defaults(func=on_create)

    parser_layers = subparsers.add_parser('layers', help='Gets latest layers dependencies for chalice-http-toolkit')
    parser_layers.add_argument('-r', dest='region', type=str, help='AWS Region', required=False, default='us-east-1', nargs=1, choices=aws_regions)
    parser_layers.add_argument('-j', dest='json', help='Format as json output', required=False, action='store_true')
    parser_layers.set_defaults(func=on_layers)

    args = parser.parse_args()
    parser.set_defaults(func=lambda args: parser.print_help())
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    args.func(args)

if __name__ == '__main__':
    main()
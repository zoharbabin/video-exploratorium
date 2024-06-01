import boto3
import time
from chalicelib.utils import logger
from chalice import Chalice, Response
from chalice.app import WebsocketEvent
from chalicelib.routes import websocket_handler
from chalicelib.middleware import handle_exceptions
from jinja2 import Environment, FileSystemLoader

app = Chalice(app_name='video-exploratorium-backend')

# Opt-in for experimental WebSocket feature
app.experimental_feature_flags.update([
    'WEBSOCKETS'
])

# Initialize the boto3 session
app.websocket_api.session = boto3.Session()

# Set up Jinja2 environment for template rendering
template_env = Environment(loader=FileSystemLoader('chalicelib/templates'))

# WebSocket handlers
@app.on_ws_message()
def message(event: WebsocketEvent):
    return websocket_handler(event, app)

@app.on_ws_connect()
def connect(event: WebsocketEvent):
    connection_id = event.connection_id
    print(f"Websocket Connection established: {connection_id}")

@app.on_ws_disconnect()
def disconnect(event: WebsocketEvent):
    connection_id = event.connection_id
    print(f"Websocket Connection closed: {connection_id}")

# Middleware for handling exceptions
@app.middleware('all')
def middleware_handler(event, get_response):
    return handle_exceptions(event, get_response)

def render_template(template_name, context):
    template = template_env.get_template(template_name)
    return template.render(context)

# Serve the main index.html
@app.route('/')
def index():
    return Response(render_template('index.html', {}), headers={'Content-Type': 'text/html'})

# Serve the about.html (if needed)
@app.route('/about')
def about():
    return Response(render_template('about.html', {}), headers={'Content-Type': 'text/html'})

# AWS Lambda handler
lambda_handler = app

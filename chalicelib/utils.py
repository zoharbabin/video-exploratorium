import sys
import json
import logging
import traceback
from datetime import datetime
from chalice import Response, WebsocketDisconnectedError
from colorlog import ColoredFormatter

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "line_number": record.lineno,
            "function_name": record.funcName
        }
        if hasattr(record, 'aws_request_id'):
            log_record['aws_request_id'] = record.aws_request_id
        if hasattr(record, 'connection_id'):
            log_record['connection_id'] = record.connection_id
        return json.dumps(log_record)

# Create a logger with a unique name
logger = logging.getLogger('video_exploratorium_logger')
logger.setLevel(logging.DEBUG)
#logger.propagate = False

# Configure the standard formatter for console output
console_formatter = ColoredFormatter(
    "\n%(asctime)s :  %(levelname)s - %(log_color)s:%(name)s:%(message)s - (Line: %(lineno)d)",
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Configure the JSON formatter for console output
json_formatter = JsonFormatter()

# Set up the console handler
#console_handler = logging.StreamHandler()
#console_handler.setFormatter(console_formatter)

# Set up the JSON handler
json_handler = logging.StreamHandler(sys.stdout)
json_handler.setFormatter(json_formatter)

# Add handlers to the logger
#logger.addHandler(console_handler)
logger.addHandler(json_handler)

# Set log levels for other loggers
logging.getLogger("pydantic_prompter").setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)

sys.stdout.flush()

def handle_error(e, websocket_api=None, connection_id=None, request_id=None):
    extra = {'aws_request_id': None}
    send_ws_error_message(websocket_api, connection_id, request_id, str(e))
    logger.error(f"Unhandled Exception: {e}", extra=extra)
    logger.error(traceback.format_exc(), extra=extra)  # Log the full traceback

def send_ws_error_message(websocket_api, connection_id, request_id, error_message):
    try:
        message = json.dumps({
            'request_id': request_id,
            'stage': 'error',
            'data': error_message
        })
        websocket_api.send(connection_id, message)
    except WebsocketDisconnectedError:
        logger.error(f"Client {connection_id} disconnected", extra={'connection_id': connection_id})

def send_ws_message(app, connection_id, request_id, stage, data):
    try:
        message = json.dumps({
            'request_id': request_id,
            'stage': stage,
            'data': data
        })
        app.websocket_api.send(connection_id, message)
    except WebsocketDisconnectedError:
        logger.error(f"Client {connection_id} disconnected", extra={'connection_id': connection_id})

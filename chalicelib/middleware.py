from chalice import Response
from chalicelib.utils import handle_error, logger

def handle_exceptions(event, get_response):
    try:
        return get_response(event)
    except Exception as e:
        logger.error(f"Exception in middleware: {e}")
        # If the event contains WebSocket connection info, pass it to handle_error.
        websocket_api = getattr(event, 'websocket_api', None)
        connection_id = getattr(event, 'connection_id', None)
        request_id = event.headers.get('request_id', None) if hasattr(event, 'headers') else None
        return handle_error(e, websocket_api, connection_id, request_id)

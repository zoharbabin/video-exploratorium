from chalice import Response
from chalicelib.utils import handle_error, logger

def handle_exceptions(event, get_response):
    try:
        return get_response(event)
    except Exception as e:
        logger.error(f"Exception in middleware: {e}")
        return handle_error(e)

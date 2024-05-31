import json
from chalicelib.utils import create_response, handle_error, send_error_message, send_progress, logger
from chalicelib.kaltura_utils import fetch_videos, validate_ks
from chalicelib.analyze import analyze_videos_ws
from chalicelib.prompters import answer_question_pp
from chalice import WebsocketDisconnectedError

def register_routes(app, cors_config):
    @app.route('/', methods=['GET'], cors=cors_config)
    def index():
        logger.info("GET / called")
        return create_response({'hello': 'world'}, request=app.current_request)

    def extract_and_validate_auth(request):
        auth_header = request.headers.get('X-Authentication')
        logger.debug(f"X-Authentication header: {auth_header}")
        if not auth_header:
            raise ValueError('X-Authentication header is required')

        pid, ks = parse_auth_header(auth_header)
        if not validate_ks(ks, pid):
            raise ValueError('Invalid Kaltura session')

        return pid, ks

def websocket_handler(event, app):
    try:
        logger.debug(f"WebSocket event: {event}")
        message = json.loads(event.body)
        action = message.get('action')
        request_id = message.get('request_id')
        headers = message.get('headers', {})

        logger.debug(f"Received message: {message}", extra={'connection_id': event.connection_id})

        if message.get('message') == "Endpoint request timed out":
            logger.info("Ignoring timeout message.")
            return

        if action == 'get_videos':
            pid, ks = extract_and_validate_auth_ws(headers, app, event.connection_id, request_id)
            category_id = message.get('categoryId')
            free_text = message.get('freeText')
            videos = fetch_videos(ks, pid, category_id, free_text)
            send_progress(app, event.connection_id, request_id, 'videos', videos)

        elif action == 'analyze_videos':
            pid, ks = extract_and_validate_auth_ws(headers, app, event.connection_id, request_id)
            selected_videos = message.get('selectedVideos', [])
            analyze_videos_ws(app, event.connection_id, request_id, selected_videos, ks, pid)

        elif action == 'ask_question':
            pid, ks = extract_and_validate_auth_ws(headers, app, event.connection_id, request_id)
            question = message.get('question')
            analysis_results = message.get('analysisResults')
            response = answer_question_pp(question=question, analysis_results=analysis_results)
            send_progress(app, event.connection_id, request_id, 'answer', response.model_dump_json())

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", extra={'connection_id': event.connection_id})
        send_error_message(app, event.connection_id, request_id, str(e))
        handle_error(e)

def extract_and_validate_auth_ws(headers, app, connection_id, request_id):
    auth_header = headers.get('X-Authentication')
    logger.debug(f"X-Authentication header: {auth_header}")
    if not auth_header:
        send_error_message(app, connection_id, request_id, 'X-Authentication header is required')
        raise ValueError('X-Authentication header is required')

    pid, ks = parse_auth_header(auth_header)
    if not validate_ks(ks, pid):
        masked_ks = f"{ks[:5]}...{ks[-5:]}"
        logger.error(f"Invalid Kaltura session (KS): {masked_ks}")
        send_error_message(app, connection_id, request_id, 'Invalid Kaltura session')
        raise ValueError('Invalid Kaltura session')

    logger.debug(f"Validated Kaltura session for pid: {pid}")
    return pid, ks

def send_error_message(app, connection_id, request_id, error_message):
    try:
        message = json.dumps({
            'request_id': request_id,
            'stage': 'error',
            'data': error_message
        })
        app.websocket_api.send(connection_id, message)
    except WebsocketDisconnectedError:
        logger.error(f"Client {connection_id} disconnected", extra={'connection_id': connection_id})

def parse_auth_header(auth_header):
    logger.debug(f"Parsing X-Authentication header: {auth_header}")
    pid_ks = auth_header.split(':')
    if len(pid_ks) != 2:
        raise ValueError('Invalid X-Authentication header format, expected partner_id:your_kaltura_session')

    pid = pid_ks[0]
    ks = pid_ks[1]
    logger.debug(f"Extracted pid: {pid}, ks: {ks[:5]}...{ks[-5:]}")
    return pid, ks

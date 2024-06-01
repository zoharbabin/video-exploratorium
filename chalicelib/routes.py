import json
import time
from chalicelib.utils import handle_error, send_ws_message, logger
from chalicelib.kaltura_utils import fetch_videos, validate_ks
from chalicelib.analyze import analyze_videos_ws
from chalicelib.prompters import answer_question_pp
from chalice import Response

# Set to track processed request IDs
processed_request_ids = set()

def register_routes(app, cors_config):
    @app.route('/', methods=['GET'], cors=cors_config)
    def index():
        logger.info("GET / called")
        return Response(
            status_code=302,
            headers={'Location': '/vidbot/'}
        )

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
    start_time = time.time()
    try:
        logger.debug(f"WebSocket event: {event}")
        message = json.loads(event.body)
        request_id = message.get('request_id')

        # Ignore timeout messages early
        if message.get('message') == "Endpoint request timed out":
            logger.info("Ignoring timeout message.")
            return

        # Check if the request_id has already been processed
        if request_id in processed_request_ids:
            logger.info(f"Ignoring duplicate request ID: {request_id}")
            return

        # Add the request_id to the processed set
        processed_request_ids.add(request_id)

        action = message.get('action')
        headers = message.get('headers', {})

        logger.debug(f"Received message: {message}", extra={'connection_id': event.connection_id})

        try:
            if action == 'get_videos':
                fetch_start_time = time.time()
                pid, ks = extract_and_validate_auth_ws(headers)
                fetch_auth_time = time.time()
                category_id = message.get('categoryId')
                free_text = message.get('freeText')
                videos = fetch_videos(ks, pid, category_id, free_text)
                fetch_videos_time = time.time()
                logger.info(f"Auth time: {fetch_auth_time - fetch_start_time}s, Fetch videos time: {fetch_videos_time - fetch_auth_time}s")
                send_ws_message(app, event.connection_id, request_id, 'videos', videos)

            elif action == 'analyze_videos':
                analyze_start_time = time.time()
                pid, ks = extract_and_validate_auth_ws(headers)
                analyze_auth_time = time.time()
                selected_videos = message.get('selectedVideos', [])
                analyze_videos_ws(app, event.connection_id, request_id, selected_videos, ks, pid)
                analyze_end_time = time.time()
                logger.info(f"Auth time: {analyze_auth_time - analyze_start_time}s, Analyze videos time: {analyze_end_time - analyze_auth_time}s")

            elif action == 'ask_question':
                ask_start_time = time.time()
                pid, ks = extract_and_validate_auth_ws(headers)
                ask_auth_time = time.time()
                question = message.get('question')
                analysis_results = message.get('analysisResults')  # Assuming analysis results are available in the session
                response = answer_question_pp(question=question, analysis_results=analysis_results)
                ask_end_time = time.time()
                logger.info(f"Auth time: {ask_auth_time - ask_start_time}s, Answer question time: {ask_end_time - ask_auth_time}s")
                send_ws_message(app, event.connection_id, request_id, 'chat_response', response.model_dump())

        finally:
            # Ensure removal of the request_id from the processed set
            processed_request_ids.discard(request_id)
            end_time = time.time()
            logger.info(f"Total time for request {request_id}: {end_time - start_time} seconds")

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", extra={'connection_id': event.connection_id})
        handle_error(e, app.websocket_api, event.connection_id, request_id)  # Use handle_error from utils.py
        processed_request_ids.discard(request_id)  # Ensure removal of the request_id from the processed set even on error
        end_time = time.time()
        logger.info(f"Total time for request {request_id} (with error): {end_time - start_time} seconds")

def extract_and_validate_auth_ws(headers):
    auth_header = headers.get('X-Authentication')
    logger.debug(f"X-Authentication header: {auth_header}")
    if not auth_header:
        raise ValueError('X-Authentication header is required')

    pid, ks = parse_auth_header(auth_header)
    validate_start_time = time.time()
    if not validate_ks(ks, pid):
        validate_end_time = time.time()
        logger.info(f"Time taken to validate KS: {validate_end_time - validate_start_time} seconds")
        masked_ks = f"{ks[:5]}...{ks[-5:]}"
        logger.error(f"Invalid Kaltura session (KS): {masked_ks}")
        raise ValueError('Invalid Kaltura session')

    logger.debug(f"Validated Kaltura session for pid: {pid}")
    return pid, ks

def parse_auth_header(auth_header):
    logger.debug(f"Parsing X-Authentication header: {auth_header}")
    pid_ks = auth_header.split(':')
    if len(pid_ks) != 2:
        raise ValueError('Invalid X-Authentication header format, expected partner_id:your_kaltura_session')

    pid = pid_ks[0]
    ks = pid_ks[1]
    logger.debug(f"Extracted pid: {pid}, ks: {ks[:5]}...{ks[-5:]}")
    return pid, ks

import json
import time
from chalice import Response
from chalice.app import WebsocketEvent
from chalicelib.prompters import answer_question_pp
from chalicelib.kaltura_utils import fetch_videos, validate_ks
from chalicelib.utils import handle_error, send_ws_message, logger
from chalicelib.analyze import analyze_videos_ws, generate_followup_questions_ws

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

def websocket_handler(event: WebsocketEvent, app):
    start_time = time.time()
    try:
        logger.debug(f"WebSocket event: {event}")
        message = json.loads(event.body)
        request_id = message.get('request_id')
        connection_id = event.connection_id

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
        pid, ks = extract_and_validate_auth_ws(headers)

        logger.debug(f"Received message (pid={pid}): {message}", extra={'connection_id': connection_id})

        try:
            if action == 'get_videos':
                category_id = message.get('categoryId')
                free_text = message.get('freeText')
                videos = fetch_videos(ks, pid, category_id, free_text)
                send_ws_message(app, connection_id, request_id, 'videos', videos, pid)

            elif action == 'analyze_videos':
                selected_videos = message.get('selectedVideos', [])
                analyze_videos_ws(app, connection_id, request_id, selected_videos, ks, pid)
                
            elif action == 'generate_followup_questions':
                transcripts = message.get('transcripts', [])
                generate_followup_questions_ws(app, connection_id, request_id, transcripts, pid)
                
            elif action == 'ask_question':
                question = message.get('question', 'Can you create a list of exploratory questions for these videos?')
                transcripts = message.get('transcripts', []) 
                prior_chat_messages = message.get('chat_history', []) 
                response = answer_question_pp(question=question, transcripts=transcripts, prior_chat_messages=prior_chat_messages)
                send_ws_message(app, connection_id, request_id, 'chat_response', response.model_dump(), pid)
                
        finally:
            # Ensure removal of the request_id from the processed set
            processed_request_ids.discard(request_id)
            end_time = time.time()
            logger.info(f"Total time for request {request_id}: {end_time - start_time} seconds")

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", extra={'connection_id': connection_id})
        handle_error(e, app.websocket_api, connection_id, request_id)  # Use handle_error from utils.py
        processed_request_ids.discard(request_id)  # Ensure removal of the request_id from the processed set even on error
        end_time = time.time()
        logger.info(f"Total time for request {request_id} (with error): {end_time - start_time} seconds")

def extract_and_validate_auth_ws(headers):
    auth_header = headers.get('X-Authentication')
    logger.debug(f"X-Authentication header: {auth_header}")
    if not auth_header:
        raise ValueError('X-Authentication header is required')

    ks = parse_auth_header(auth_header)
    validate_start_time = time.time()
    ks = parse_auth_header(auth_header)
    ks_valid, pid = validate_ks(ks)
    if not ks_valid:
        validate_end_time = time.time()
        logger.info(f"Time taken to validate KS: {validate_end_time - validate_start_time} seconds")
        masked_ks = f"{ks[:5]}...{ks[-5:]}"
        logger.error(f"Invalid Kaltura session (KS): {masked_ks}")
        raise ValueError('Invalid Kaltura session')

    logger.debug(f"Validated Kaltura session for pid: {pid}")
    return pid, ks

def parse_auth_header(auth_header):
    logger.debug(f"Parsing X-Authentication header: {auth_header}")

    # The auth_header should now only contain the ks value directly.
    ks = auth_header.strip()
    if not ks:
        raise ValueError('Invalid X-Authentication header format, expected your_kaltura_session')

    logger.debug(f"Extracted ks: {ks[:5]}...{ks[-5:]}")
    return ks

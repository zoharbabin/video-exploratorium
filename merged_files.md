I will provide below my entire project files.
This project is a lambda app deployed using Chalice, and a simple python script that deploys the static files into S3/Cloudfront.
Please review the entire project files in great detail, index and understand all of it.
I will then provide you with further instructions.

# Merged Files

requirements.txt:

```
# backend/videos-analysis-chat/requirements.txt
lxml
python-dotenv==1.0.0
chalice==1.27.0
colorlog==6.8.2
pydantic==2.7.1
requests==2.32.2
pydantic-settings>=2.1.0
KalturaApiClient==20.7.0
pydantic-prompter==0.1.33
pydantic-prompter[bedrock]==0.1.33
websockets==10.4
Jinja2
```

__init__.py:

```

```

app.py:

```
import os
import boto3
from chalicelib.utils import logger
from chalice import Chalice, Response
from chalicelib.routes import register_routes, websocket_handler
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
def message(event):
    return websocket_handler(event, app)

@app.on_ws_connect()
def connect(event):
    print(f"Client connected: {event}")

@app.on_ws_disconnect()
def disconnect(event):
    print(f"Client disconnected: {event}")

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

```

deploy_static.py:

```
import boto3
import os
import time
from pathlib import Path
import mimetypes

AWS_REGION = 'us-east-1'
S3_BUCKET_NAME = 'zoharbabintest'
CLOUDFRONT_DISTRIBUTION_ID = 'E1EJTL378WS6GY'
LOCAL_STATIC_DIR = './static'

s3_client = boto3.client('s3', region_name=AWS_REGION)
cloudfront_client = boto3.client('cloudfront', region_name=AWS_REGION)

def upload_files_to_s3():
    for root, dirs, files in os.walk(LOCAL_STATIC_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            s3_key = str(Path(file_path).relative_to(LOCAL_STATIC_DIR))
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = 'binary/octet-stream'  # default fallback

            print(f'Uploading {file_path} to s3://{S3_BUCKET_NAME}/{s3_key} with ContentType {content_type}')
            s3_client.upload_file(
                file_path,
                S3_BUCKET_NAME,
                s3_key,
                ExtraArgs={'ContentType': content_type}
            )

def invalidate_cloudfront_cache():
    invalidation = cloudfront_client.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION_ID,
        InvalidationBatch={
            'Paths': {
                'Quantity': 1,
                'Items': ['/*']
            },
            'CallerReference': str(time.time())
        }
    )
    print(f'Invalidation ID: {invalidation["Invalidation"]["Id"]}')

if __name__ == "__main__":
    upload_files_to_s3()
    invalidate_cloudfront_cache()

```

chalicelib/prompters.py:

```
# /backend/prompters.py
from typing import List
from pydantic import BaseModel, Field
from pydantic_prompter import Prompter

class Section(BaseModel):
    title: str = Field(description="Short title of the section.")
    summary: str = Field(description="Detailed summary of the section. Up to 4 sentences long.")
    start_sentence: str = Field(description="First sentence from the transcript that begins the section.")
    start_time: int = Field(description="Start time of the section in seconds.")

class Insight(BaseModel):
    text: str = Field(description="A short text describing the insight extracted from this segment. Up to 1 sentences long.")
    start_time: int = Field(description="Start time of the insight in seconds.")

class Person(BaseModel):
    name: str = Field(description="The name of the person (or identifier 'Person1', 'Person2', etc., if names are not available).")

class VideoSummary(BaseModel):
    entry_id: str = Field(description="The ID of the video entry.")
    full_summary: str = Field(description="Comprehensive summary of the video. Up to 6 sentences long.")
    sections: List[Section] = Field(description="List of sections identified in the video.")
    insights: List[Insight] = Field(description="List of main insights discussed in the video.")
    people: List[Person] = Field(description="List of people identified in the video, with timestamps of when they first spoke.")
    primary_topics: List[str] = Field(description="Primary topics discussed in the video, topics should be described in up to 6 words per primary topic.")

class CrossVideoInsights(BaseModel):
    shared_insights: List[str] = Field(description="Shared insights across all analyzed videos. Up to 4 sentences long per shared insight.")
    common_themes: List[str] = Field(description="Common themes across videos. Up to 1 sentence long per common theme.")
    opposing_views: List[str] = Field(description="Opposing views across videos. Up to 2 sentence long per opposing view.")
    sentiments: List[str] = Field(description="Sentiments across the videos. Up to 1 sentence per sentiment.")

class QAResponse(BaseModel):
    answer: str = Field(description="The answer to the user's question based on the video content.")

@Prompter(llm="bedrock", model_name="anthropic.claude-3-sonnet-20240229-v1:0", jinja=True, model_settings={
    "max_tokens": 4096,
    "temperature": 0,
    "top_p": 0.999,
    "top_k": 1,
    "stop_sequences": ["<|end_of_json|>"]
})
def combine_chunk_analyses_pp(chunk_summaries: List[VideoSummary]) -> VideoSummary:
    """
    - user:
        Below are multiple chunks of an analyzed video transcript. 
        Your task is to combine these chunk analyses into a single, comprehensive analysis of the whole video, according to the guidelines.
        

        ## Guidelines:

        1. Provide a comprehensive analysis of the entire video transcript based on the provided chunk analyses.
        2. Identify and list all main sections and insights across all chunks.
        3. Identify and list all people mentioned across all chunks.
        4. Ensure that the combined analysis is coherent and covers all aspects of the video.
        5. At the end of your output, imediately after the final closing curly brace of the json object, include: "<|end_of_json|>". This will signal the end of the output.


        ## Chunk Analyses:

        {{ chunk_summaries }}

    """

@Prompter(llm="bedrock", model_name="anthropic.claude-3-sonnet-20240229-v1:0", jinja=True, model_settings={
    "max_tokens": 4096,
    "temperature": 0,
    "top_p": 0.999,
    "top_k": 1,
    "stop_sequences": ["<|end_of_json|>"]
})
def analyze_chunk_pp(video_entry_id: str, chunk_transcript: str) -> VideoSummary:
    """
    - user:
        You will be given a video ID, and a chunk of its transcript (in JSON format) below. 
        Your task is to analyze the chunk based on the provided transcript, according to the guidelines.
        

        ## Guidelines:

        1. Provide a comprehensive summary of the transcript chunk.
        2. Identify and list all main sections and insights of the transcript chunk.
        3. Identify and list all people mentioned in the transcript chunk.
        4. At the end of your output, imediately after the final closing curly brace of the json object, include: "<|end_of_json|>". This will signal the end of the output.
        

        ## Video ID: {{ video_entry_id }}

        
        ## The Transcript Chunk:
        {{ chunk_transcript }}

    """

@Prompter(llm="bedrock", model_name="anthropic.claude-3-sonnet-20240229-v1:0", jinja=True, model_settings={
    "max_tokens": 4096,
    "temperature": 0,
    "top_p": 0.999,
    "top_k": 1,
    "stop_sequences": ["<|end_of_json|>"]
})
def cross_video_insights_pp(analysis_results: List[str]) -> CrossVideoInsights:
    """
    - user:
        Below are summaries of multiple video transcripts. 
        Your task is to provide a cross-videos analysis based on the guidelines.

        ## Guidelines:
        
        1. Combine the input individual video summaries into a combined, single, comprehensive analysis according to the guidelines. 
        2. Your analysis should includea the shared insights, common themes, opposing views and sentiments that span across the provided input video summaries.
        3. At the end of your output, imediately after the final closing curly brace of the json object, include: "<|end_of_json|>". This will signal the end of the output.

        
        ## Input Video Summaries:
        
        {{ analysis_results }}

    """

@Prompter(llm="bedrock", model_name="anthropic.claude-3-sonnet-20240229-v1:0", jinja=True, model_settings={
    "max_tokens": 4096,
    "temperature": 0,
    "top_p": 0.999,
    "top_k": 1
})
def answer_question_pp(question: str, analysis_results: List[VideoSummary]) -> QAResponse:
    """
    - system: 
        You are a data enrichment API. 
        Your response should be in a valid JSON format, which its schema is specified in the `Response JSON Schema` section below. 
        DO NOT add any text or explanations, only respond with the valid JSON.

        ## Response JSON Schema
        ```
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "The answer to the user's question based on the video content."
                }
            },
            "required": ["answer"]
        }
        ```

    - user:
        Based on the provided analysis results, answer the following question.

        ## Question
        {{ question }}

        ## Analysis Results
        {{ analysis_results }}
    """

```

chalicelib/transcript_utils.py:

```
import json

def chunk_transcript(data, max_chars=150000, overlap=10000):
    def get_json_size(segment):
        return len(json.dumps(segment))

    def add_segment(segments, segment, text_buffer):
        if text_buffer:
            segment['content'].append({'text': text_buffer.strip()})
        segments.append(segment)

    segments = []
    current_segment = None
    text_buffer = ''
    
    for entry in data:
        for content in entry['content']:
            sentences = content['text'].split('\n')
            for sentence in sentences:
                if sentence:
                    sentence += '\n'
                    if current_segment is None:
                        current_segment = {'startTime': entry['startTime'], 'endTime': entry['endTime'], 'content': []}
                    
                    temp_segment = json.loads(json.dumps(current_segment))
                    temp_segment['content'].append({'text': text_buffer + sentence})
                    
                    if get_json_size(temp_segment) > max_chars:
                        add_segment(segments, current_segment, text_buffer)
                        text_buffer = text_buffer[-overlap:]
                        current_segment = {'startTime': entry['startTime'], 'endTime': entry['endTime'], 'content': []}
                    
                    text_buffer += sentence
    
    if text_buffer and current_segment:
        add_segment(segments, current_segment, text_buffer)

    return segments

```

chalicelib/config.py:

```
import os
from dotenv import load_dotenv
from chalicelib.utils import logger

# Load .env file from the specified path
env_path = os.path.join(os.path.dirname(__file__), '../.env')
logger.info(f"Loading environment variables from {env_path}")
load_dotenv(dotenv_path=env_path)

class Config:
    def __init__(self):
        # Load from environment variables
        self.service_url = os.getenv('SERVICE_URL', 'https://cdnapi-ev.kaltura.com/')
        
        logger.info(f"Service URL: {self.service_url}")

config = Config()

```

chalicelib/kaltura_utils.py:

```
import time
import json
import requests
import traceback
from KalturaClient import KalturaClient, KalturaConfiguration
from KalturaClient.Plugins.Core import KalturaSessionType, KalturaFilterPager, KalturaMediaType, KalturaSessionInfo
from KalturaClient.Plugins.Caption import KalturaCaptionAssetFilter, KalturaCaptionAssetOrderBy, KalturaLanguage
from KalturaClient.Plugins.ElasticSearch import (
    KalturaESearchEntryParams, KalturaESearchEntryOperator, KalturaESearchOperatorType,
    KalturaESearchCaptionItem, KalturaESearchCaptionFieldName, KalturaESearchItemType,
    KalturaESearchEntryItem, KalturaESearchEntryFieldName, KalturaESearchOrderBy,
    KalturaESearchEntryOrderByItem, KalturaESearchEntryOrderByFieldName, KalturaESearchSortOrder,
    KalturaESearchCategoryEntryItem, KalturaESearchCategoryEntryFieldName, KalturaCategoryEntryStatus, KalturaESearchUnifiedItem
)
from chalicelib.config import config
from chalicelib.utils import logger, send_progress
from chalicelib.transcript_utils import chunk_transcript

def get_kaltura_client(ks, pid):
    config_kaltura = KalturaConfiguration(pid)
    config_kaltura.serviceUrl = config.service_url
    client = KalturaClient(config_kaltura)
    client.setKs(ks)
    return client

def validate_ks(ks, pid):
    try:
        client = get_kaltura_client(ks, pid)
        session_info: KalturaSessionInfo = client.session.get()
        is_pid_valid = int(session_info.partnerId) - int(pid) == 0
        current_time = time.time()
        is_ks_not_expired = session_info.expiry > current_time
        logger.debug(f"Validating Kaltura session: pid: {is_pid_valid} [{pid}/{session_info.partnerId}],  ks_expiry_valid: {is_ks_not_expired}")
        return is_pid_valid and is_ks_not_expired
    except Exception as e:
        logger.error(f"Invalid Kaltura session (KS): {e}")
        return False

def get_english_captions(entry_id, ks, pid):
    client = get_kaltura_client(ks, pid)
    logger.debug(f"Fetching captions for entry ID: {entry_id}")
    caption_filter = KalturaCaptionAssetFilter()
    caption_filter.entryIdEqual = entry_id
    caption_filter.languageEqual = KalturaLanguage.EN
    caption_filter.orderBy = KalturaCaptionAssetOrderBy.CREATED_AT_DESC
    pager = KalturaFilterPager()
    result = client.caption.captionAsset.list(caption_filter, pager)
    captions = [{'id': caption.id, 'label': caption.label, 'language': caption.language} for caption in result.objects]
    logger.debug(f"Captions for entry ID {entry_id}: {captions}")
    return captions

def fetch_videos(ks, pid, category_ids=None, free_text=None):
    client = get_kaltura_client(ks, pid)
    search_params = KalturaESearchEntryParams()
    search_params.orderBy = KalturaESearchOrderBy()
    order_item = KalturaESearchEntryOrderByItem()
    order_item.sortField = KalturaESearchEntryOrderByFieldName.UPDATED_AT
    order_item.sortOrder = KalturaESearchSortOrder.ORDER_BY_DESC
    search_params.orderBy.orderItems = [order_item]

    search_params.searchOperator = KalturaESearchEntryOperator()
    search_params.searchOperator.operator = KalturaESearchOperatorType.AND_OP
    search_params.searchOperator.searchItems = []

    caption_item = KalturaESearchCaptionItem()
    caption_item.fieldName = KalturaESearchCaptionFieldName.CONTENT
    caption_item.itemType = KalturaESearchItemType.EXISTS
    search_params.searchOperator.searchItems.append(caption_item)

    entry_item = KalturaESearchEntryItem()
    entry_item.fieldName = KalturaESearchEntryFieldName.MEDIA_TYPE
    entry_item.addHighlight = False
    entry_item.itemType = KalturaESearchItemType.EXACT_MATCH
    entry_item.searchTerm = KalturaMediaType.VIDEO
    search_params.searchOperator.searchItems.append(entry_item)

    if category_ids is not None:
        category_item = KalturaESearchCategoryEntryItem()
        category_item.categoryEntryStatus = KalturaCategoryEntryStatus.ACTIVE
        category_item.fieldName = KalturaESearchCategoryEntryFieldName.ANCESTOR_ID
        category_item.addHighlight = False
        category_item.itemType = KalturaESearchItemType.EXACT_MATCH
        category_item.searchTerm = category_ids
        search_params.searchOperator.searchItems.append(category_item)

    if free_text is not None:
        unified_item = KalturaESearchUnifiedItem()
        unified_item.searchTerm = free_text
        unified_item.itemType = KalturaESearchItemType.PARTIAL
        search_params.searchOperator.searchItems.append(unified_item)

    pager = KalturaFilterPager()
    pager.pageIndex = 1
    pager.pageSize = 4

    result = client.elasticSearch.eSearch.searchEntry(search_params, pager)

    videos = []
    for entry in result.objects:
        entry_info = {
            "entry_id": str(entry.object.id),
            "entry_name": str(entry.object.name),
            "entry_description": str(entry.object.description or ""),
            "entry_media_type": int(entry.object.mediaType.value or 0),
            "entry_media_date": int(entry.object.createdAt or 0),
            "entry_ms_duration": int(entry.object.msDuration or 0),
            "entry_last_played_at": int(entry.object.lastPlayedAt or 0),
            "entry_application": str(entry.object.application or ""),
            "entry_creator_id": str(entry.object.creatorId or ""),
            "entry_tags": str(entry.object.tags or ""),
            "entry_reference_id": str(entry.object.referenceId or "")
        }
        videos.append(entry_info)

    return videos

def get_json_transcript(caption_asset_id, ks, pid):
    try:
        client = get_kaltura_client(ks, pid)
        cap_json_url = client.caption.captionAsset.serveAsJson(caption_asset_id)
        logger.debug(f"Caption JSON URL: {cap_json_url}")
        response = requests.get(cap_json_url)
        response.raise_for_status()
        transcript = response.json()['objects']
        logger.debug(f"Raw JSON Captions: captionAssetId: {caption_asset_id}: {json.dumps(transcript)}")

        segmented_transcripts = chunk_transcript(transcript)
        logger.debug(f"Segmented transcripts: {segmented_transcripts}")
        return segmented_transcripts
    except requests.RequestException as e:
        logger.error(f"HTTP error while fetching captions: {e}")
        logger.error(traceback.format_exc())
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {e}")
        logger.error(traceback.format_exc())
    except Exception as e:
        logger.error(f"An error occurred while getting captions: {e}")
        logger.error(traceback.format_exc())
    return []

```

chalicelib/utils.py:

```
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

def create_response(body, status_code=200, request=None):
    headers = {'Content-Type': 'application/json'}
    return Response(body=json.dumps(body), status_code=status_code, headers=headers)

def handle_error(e, request=None):
    extra = {'aws_request_id': getattr(request.context, 'aws_request_id', None) if request else None}
    logger.error(f"Unhandled Exception: {e}", extra=extra)
    logger.error(traceback.format_exc(), extra=extra)  # Log the full traceback
    return create_response({'error': str(e)}, status_code=500, request=request)

def send_progress(app, connection_id, request_id, stage, data):
    try:
        message = json.dumps({
            'request_id': request_id,
            'stage': stage,
            'data': data
        })
        app.websocket_api.send(connection_id, message)
    except WebsocketDisconnectedError:
        logger.error(f"Client {connection_id} disconnected", extra={'connection_id': connection_id})

```

chalicelib/middleware.py:

```
from chalice import Response
from chalicelib.utils import handle_error, logger

def handle_exceptions(event, get_response):
    try:
        return get_response(event)
    except Exception as e:
        logger.error(f"Exception in middleware: {e}")
        return handle_error(e)

```

chalicelib/analyze.py:

```
import json
import traceback
from chalicelib.kaltura_utils import get_english_captions, get_json_transcript
from chalicelib.prompters import analyze_chunk_pp, combine_chunk_analyses_pp, cross_video_insights_pp, VideoSummary, CrossVideoInsights
from chalicelib.utils import logger, send_progress

def analyze_videos_ws(app, connection_id, request_id, selected_videos, ks, pid):
    try:
        all_analysis_results = []
        all_transcripts = []

        for video_id in selected_videos:
            logger.info(f"Processing video ID: {video_id}")
            captions = get_english_captions(video_id, ks, pid)
            
            if captions:
                caption = captions[0]
                logger.info(f"Processing caption ID: {caption['id']} for video ID: {video_id}")
                segmented_transcripts = get_json_transcript(caption['id'], ks, pid)
                logger.debug(f"Segmented transcripts for caption ID {caption['id']}: {segmented_transcripts}")

                if not segmented_transcripts:
                    logger.error(f"No caption content found for caption ID: {caption['id']}")
                    continue

                chunk_summaries = []
                total_chunks = len(segmented_transcripts)
                for index, segment in enumerate(segmented_transcripts):
                    segment_text = json.dumps(segment)
                    logger.debug(f"Segment {index + 1}/{total_chunks} content for chunk analysis: {segment_text[:500]}...")
                    try:
                        chunk_summary: VideoSummary = analyze_chunk_pp(video_entry_id=video_id, chunk_transcript=segment_text)
                        chunk_json = chunk_summary.model_dump_json()
                        logger.info(f"Chunk {index + 1}/{total_chunks} analysis result: {chunk_json[:200]}...{chunk_json[-200:]}")
                        chunk_summaries.append(chunk_summary)
                        send_progress(app, connection_id, request_id, 'chunk_progress', {
                            'video_id': video_id,
                            'chunk_index': index + 1,
                            'total_chunks': total_chunks,
                            'chunk_summary': chunk_json
                        })
                    except Exception as e:
                        logger.error(f"Error during chunk analysis for video ID {video_id}, chunk {index + 1}: {e}")
                        logger.error(traceback.format_exc())

                if chunk_summaries:
                    try:
                        total_chunks = len(chunk_summaries)
                        if total_chunks > 1:
                            for i, chunk_summary in enumerate(chunk_summaries):
                                try:
                                    json_data = chunk_summary.model_dump_json()
                                    json.loads(json.dumps(json_data))
                                    logger.info(f"Valid JSON Chunk Summary {i + 1}/{total_chunks}")
                                except Exception as e:
                                    logger.error(f"Invalid JSON in chunk summary {i + 1}/{total_chunks}: {e}")
                                    logger.debug(f"Chunk Summary {i + 1}/{total_chunks}: {json.dumps(json_data)}")
                                    continue

                            chunk_summaries_json = [summary.model_dump_json() for summary in chunk_summaries]
                            logger.info(f"Creating a combined analysis across chunks for video ID {video_id}")
                            combined_summary: VideoSummary = combine_chunk_analyses_pp(chunk_summaries=chunk_summaries_json)
                            combined_summary_dict = combined_summary.model_dump()
                            combined_summary_json = combined_summary.model_dump_json()
                            logger.info(f"Combined chunk analysis result for video ID {video_id}: {combined_summary_json[:500]}...{combined_summary_json[-500:]}")
                            all_analysis_results.append(combined_summary_dict)
                            all_transcripts.extend(segmented_transcripts)
                            send_progress(app, connection_id, request_id, 'combined_summary', combined_summary_json)
                        else:
                            logger.info(f"Only one chunk found for video ID {video_id}, skipping combining analysis.")
                            combined_summary_dict = chunk_summaries[0].model_dump()
                            all_analysis_results.append(combined_summary_dict)
                            all_transcripts.extend(segmented_transcripts)
                            send_progress(app, connection_id, request_id, 'combined_summary', combined_summary_dict)
                    except Exception as e:
                        logger.error(f"Error during combining chunk analyses for video ID {video_id}: {e}")
                        logger.error(traceback.format_exc())
                else:
                    logger.error(f"No chunk analysis results found for video ID {video_id}.")
        
        if not all_analysis_results:
            logger.error("No analysis results found.")
            send_progress(app, connection_id, request_id, 'error', 'No analysis results found')
            return

        response = {
            "individual_results": all_analysis_results
        }

        if len(selected_videos) > 1:
            try:
                logger.info(f"Creating videos analysis for {selected_videos}")
                full_summaries = [result["full_summary"] for result in all_analysis_results]
                cross_video_insights: CrossVideoInsights = cross_video_insights_pp(analysis_results=full_summaries)
                cross_video_insights_dict = cross_video_insights.model_dump()
                logger.debug(f"Cross video insights result: {cross_video_insights_dict}")
                response["cross_video_insights"] = cross_video_insights_dict
                send_progress(app, connection_id, request_id, 'cross_video_insights', cross_video_insights_dict)
            except Exception as e:
                logger.error(f"Error during cross video insights analysis: {e}")
                logger.error(traceback.format_exc())

        logger.info("Video analysis complete")
        send_progress(app, connection_id, request_id, 'completed', response)

    except Exception as e:
        logger.error(f"Error during video analysis: {e}")
        logger.error(traceback.format_exc())
        send_progress(app, connection_id, request_id, 'error', str(e))

```

chalicelib/routes.py:

```
import json
from chalicelib.utils import create_response, handle_error, send_progress, logger
from chalicelib.kaltura_utils import fetch_videos, get_english_captions, get_json_transcript, validate_ks
from chalicelib.analyze import analyze_videos_ws
from chalicelib.prompters import answer_question_pp

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

        if action == 'get_videos':
            pid, ks = extract_and_validate_auth_ws(headers)
            category_id = message.get('categoryId')
            free_text = message.get('freeText')
            videos = fetch_videos(ks, pid, category_id, free_text)
            send_progress(app, event.connection_id, request_id, 'videos', videos)

        elif action == 'analyze_videos':
            pid, ks = extract_and_validate_auth_ws(headers)
            selected_videos = message.get('selectedVideos', [])
            analyze_videos_ws(app, event.connection_id, request_id, selected_videos, ks, pid)

        elif action == 'ask_question':
            pid, ks = extract_and_validate_auth_ws(headers)
            question = message.get('question')
            analysis_results = message.get('analysisResults')
            response = answer_question_pp(question=question, analysis_results=analysis_results)
            send_progress(app, event.connection_id, request_id, 'answer', response.model_dump_json())

    except Exception as e:
        logger.error(f"WebSocket handler error: {e}", extra={'connection_id': event.connection_id})
        handle_error(e)

def extract_and_validate_auth_ws(headers):
    auth_header = headers.get('X-Authentication')
    logger.debug(f"X-Authentication header: {auth_header}")
    if not auth_header:
        raise ValueError('X-Authentication header is required')

    pid, ks = parse_auth_header(auth_header)
    if not validate_ks(ks, pid):
        logger.error(f"Invalid Kaltura session (KS): {ks}")
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
    logger.debug(f"Extracted pid: {pid}, ks: {ks}")
    return pid, ks

```

chalicelib/templates/index.html:

```
{% extends 'base.html' %}

{% block content %}
<div id="status" class="alert alert-info">Connecting to WebSocket...</div>
<div class="container">
    <div class="card">
        <div class="card-header" onclick="toggleCard(this)">
            <h3>
                <span class="toggle-icon">&#9654;</span>
                Search Videos
            </h3>
        </div>
        <div class="card-body">
            <div class="form-group d-flex justify-content-between">
                <input type="text" id="category-id-text-input" class="form-control mr-2 flex-grow-1" placeholder="Enter category ID">
                <input type="text" id="free-text-input" class="form-control mr-2 flex-grow-1" placeholder="Enter free text">
                <button id="get-videos-category-text-button" class="btn btn-primary">Search Videos</button>
            </div>
        </div>
    </div>

    <div class="card mt-3">
        <div class="card-header" onclick="toggleCard(this)">
            <h3>
                <span class="toggle-icon">&#9654;</span>
                Analyze Videos
            </h3>
        </div>
        <div class="card-body">
            <div class="form-group d-flex justify-content-between">
                <input type="text" id="video-ids-input" class="form-control mr-2 flex-grow-1" placeholder="Enter video IDs (comma separated)">
                <button id="analyze-videos-button" class="btn btn-primary">Analyze Videos</button>
            </div>
        </div>
    </div>

    <div class="card mt-5">
        <div class="card-header" onclick="toggleCard(this)">
            <h3>
                <span class="toggle-icon">&#9654;</span>
                Videos
            </h3>
        </div>
        <div class="card-body">
            <ul id="video-list-items" class="list-group"></ul>
        </div>
    </div>

    <div id="progress-section" class="card mt-5" style="display: none;">
        <div class="card-header" onclick="toggleCard(this)">
            <h3>
                <span class="toggle-icon">&#9654;</span>
                Analysis Progress
            </h3>
        </div>
        <div class="card-body">
            <div class="progress">
                <div id="progress-bar" class="progress-bar progress-bar-animated" role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
            </div>
            <div id="progress-insights" class="mt-3"></div>
        </div>
    </div>

    <div id="analysis-results" style="display: none;">
        <div class="card mt-5">
            <div class="card-header" onclick="toggleCard(this)">
                <h3>
                    <span class="toggle-icon">&#9654;</span>
                    Combined Summary
                </h3>
            </div>
            <div class="card-body">
                <div id="combined-summary-content" class="bg-dark text-white p-3 border rounded"></div>
            </div>
        </div>

        <div class="card mt-5">
            <div class="card-header" onclick="toggleCard(this)">
                <h3>
                    <span class="toggle-icon">&#9654;</span>
                    Cross Video Insights
                </h3>
            </div>
            <div class="card-body">
                <div id="cross-video-insights-content" class="bg-dark text-white p-3 border rounded"></div>
            </div>
        </div>

        <div class="card mt-5">
            <div class="card-header" onclick="toggleCard(this)">
                <h3>
                    <span class="toggle-icon">&#9654;</span>
                    Answer
                </h3>
            </div>
            <div class="card-body">
                <div id="answer-content" class="bg-dark text-white p-3 border rounded"></div>
            </div>
        </div>
    </div>

    <div class="card mt-5">
        <div class="card-header" onclick="toggleCard(this)">
            <h3>
                <span class="toggle-icon">&#9654;</span>
                Errors
            </h3>
        </div>
        <div class="card-body">
            <ul id="error-list" class="list-group"></ul>
        </div>
    </div>
</div>
{% endblock %}

```

chalicelib/templates/about.html:

```
{% extends 'base.html' %}

{% block content %}
<h2>About Video Exploratorium</h2>
<p>Welcome to Video Exploratorium, a place where you can explore and analyze videos seamlessly.</p>
{% endblock %}

```

chalicelib/templates/base.html:

```
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Exploratorium</title>
    <link rel="icon" type="image/x-icon" href="https://dkq8kg1ng3wtk.cloudfront.net/favicon.ico">
    <link rel="stylesheet" href="https://dkq8kg1ng3wtk.cloudfront.net/styles.css">
</head>
<body class="dark-mode">
    <header class="header">
        <div class="logo">Video Exploratorium</div>
        <nav class="nav">
            <ul>
                <li><a href="/">Home</a></li>
                <li><a href="/about">About</a></li>
            </ul>
        </nav>
    </header>
    <main class="main">
        {% block content %}
        {% endblock %}
    </main>
    <footer class="footer">
        <p>&copy; 2024 Video Exploratorium. All rights reserved.</p>
    </footer>
    <script src="https://dkq8kg1ng3wtk.cloudfront.net/scripts.js"></script>
</body>
</html>

```

static/styles.css:

```
body {
    font-family: Arial, sans-serif;
    background-color: #121212;
    color: #e0e0e0;
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #1f1f1f;
    color: #fff;
    padding: 1rem;
}

.logo {
    font-size: 1.5rem;
    font-weight: bold;
}

.nav ul {
    list-style: none;
    padding: 0;
    display: flex;
    gap: 1rem;
}

.nav ul li {
    margin: 0;
}

.nav ul li a {
    color: #bb86fc;
    text-decoration: none;
}

.main {
    padding: 2rem;
}

.card {
    background-color: #1f1f1f;
    padding: 1rem;
    margin-bottom: 1rem;
    border-radius: 0.5rem;
}

.card h3 {
    margin-top: 0;
}

.form-group {
    margin-bottom: 1rem;
}

.alert {
    color: #000;
}

.alert-info {
    background-color: #bb86fc;
}

.alert-success {
    background-color: #03dac6;
}

.alert-danger {
    background-color: #cf6679;
}

.list-group-item {
    display: flex;
    align-items: center;
    margin-bottom: 0.5rem;
    background-color: #2c2c2c;
    border: 1px solid #333;
    padding: 0.5rem;
    height: 80px;
}

.list-group-item img {
    width: 80px;
    height: 80px;
    margin-right: 1rem;
    object-fit: contain;
}

.list-group-item-danger {
    background-color: #cf6679;
}

.btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 0.25rem;
    border: none;
    cursor: pointer;
    text-align: center;
}

.btn-primary {
    background-color: #bb86fc;
    color: #fff;
}

.btn-primary:hover {
    background-color: #3700b3;
}

.btn-secondary {
    background-color: #03dac6;
    color: #fff;
}

.btn-secondary:hover {
    background-color: #018786;
}

.bg-dark {
    background-color: #2c2c2c;
}

.text-white {
    color: #e0e0e0;
}

.footer {
    background-color: #1f1f1f;
    color: #fff;
    text-align: center;
    padding: 1rem;
    position: fixed;
    bottom: 0;
    width: 100%;
}

.progress {
    background-color: #333;
    border-radius: 0.25rem;
    overflow: hidden;
    position: relative;
}

.progress-bar {
    background-color: #bb86fc;
    height: 1rem;
    animation: progress-bar-stripes 1s linear infinite;
    transition: width 0.4s ease;
}

@keyframes progress-bar-stripes {
    from { background-position: 1rem 0; }
    to { background-position: 0 0; }
}

.progress-bar-animated {
    background-color: #bb86fc;
    height: 1rem;
    width: 0%;
    animation: progress-animation 2s infinite;
}

@keyframes progress-animation {
    0% { width: 0%; }
    50% { width: 100%; }
    100% { width: 0%; }
}

#progress-insights {
    margin-top: 1rem;
}

.d-flex {
    display: flex;
    align-items: center;
}

.mr-2 {
    margin-right: 0.5rem;
}

.card-header {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #2c2c2c;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #333;
}

.card-body {
    display: none;
}

.card-header h3 {
    margin: 0;
    font-size: 1.25rem;
}

.toggle-icon {
    font-size: 1rem;
    margin-right: 1rem;
    transition: transform 0.3s;
}

.card.expanded .card-body {
    display: block;
}

.card.expanded .toggle-icon {
    transform: rotate(90deg);
}

.d-flex {
    display: flex;
    align-items: center;
}

.justify-content-between {
    justify-content: space-between;
}

.mr-2 {
    margin-right: 0.5rem;
}

.flex-grow-1 {
    flex-grow: 1;
}

.card-header {
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #2c2c2c;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #333;
}

.card-body {
    display: none;
}

.card-header h3 {
    margin: 0;
    font-size: 1.25rem;
}

.toggle-icon {
    font-size: 1rem;
    margin-right: 1rem;
    transition: transform 0.3s;
}

.card.expanded .card-body {
    display: block;
}

.card.expanded .toggle-icon {
    transform: rotate(90deg);
}

```

static/scripts.js:

```
document.addEventListener("DOMContentLoaded", function () {
    const socket = new WebSocket('wss://fyocljsr02.execute-api.us-east-1.amazonaws.com/vidbot/');
    let totalChunks = 0;
    let processedChunks = 0;

    socket.onopen = function () {
        showStatus('Connected to the server', 'alert-success');
    };

    socket.onclose = function () {
        showStatus('Disconnected from the server', 'alert-danger');
    };

    socket.onerror = function (error) {
        console.error('WebSocket Error:', error);
        showStatus('WebSocket Error', 'alert-danger');
    };

    socket.onmessage = function (event) {
        const message = JSON.parse(event.data);
        console.log('Received message:', message); // Debugging information
        handleServerMessage(message);
    };

    function getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        return {
            pid: params.get('pid'),
            ks: params.get('ks')
        };
    }

    function sendMessage(action, data) {
        const { pid, ks } = getUrlParams();
        if (!pid || !ks) {
            console.error('PID and KS parameters are required');
            return;
        }

        const message = {
            action: action,
            request_id: generateUUID(),
            headers: {
                'X-Authentication': `${pid}:${ks}`
            },
            ...data
        };
        if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(message));
            showStatus('Message sent to the server...', 'alert-info');
        } else {
            console.error('WebSocket is not open. Ready state: ' + socket.readyState);
        }
    }

    function handleServerMessage(message) {
        showStatus('Response received from the server', 'alert-success');

        switch (message.stage) {
            case 'videos':
                displayVideos(message.data);
                expandCard(document.querySelector('#video-list-items').closest('.card'));
                break;
            case 'chunk_progress':
                updateProgress(message.data);
                break;
            case 'combined_summary':
                displayCombinedSummary(message.data);
                break;
            case 'cross_video_insights':
                displayCrossVideoInsights(message.data);
                break;
            case 'completed':
                displayFinalResults(message.data);
                const analysisResultsCard = document.querySelector('#analysis-results').closest('.card');
                console.log('Expanding analysis results card:', analysisResultsCard); // Debugging information
                expandCard(analysisResultsCard);
                collapseOtherCards(analysisResultsCard);
                break;
            case 'answer':
                displayAnswer(message.data);
                break;
            case 'error':
                displayError(message.data);
                break;
            default:
                console.warn('Unknown message stage:', message.stage);
        }
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0,
                v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function formatTime(seconds) {
        const date = new Date(0);
        date.setSeconds(seconds);
        return date.toISOString().substr(11, 8);
    }

    function displayVideos(videos) {
        const videoList = document.getElementById('video-list-items');
        const { pid } = getUrlParams();
        if (videoList) {
            videoList.innerHTML = '';
            videos.forEach(video => {
                const li = document.createElement('li');
                li.classList.add('list-group-item');
                li.innerHTML = `
                    <img src="https://cfvod.kaltura.com/p/${pid}/sp/${pid}00/thumbnail/entry_id/${video.entry_id}/width/80/type/2/bgcolor/000000" alt="Thumbnail">
                    <div>
                        <strong>${video.entry_name}</strong> (${video.entry_id})<br>
                        <small>${video.entry_description}</small>
                        <br><small>Zoom Recording ID: ${video.entry_reference_id}</small>
                    </div>`;
                videoList.appendChild(li);
            });
        }
    }

    function startProgressBar() {
        const progressSection = document.getElementById('progress-section');
        const progressBar = document.getElementById('progress-bar');
        progressSection.style.display = 'block';
        progressBar.classList.add('progress-bar-animated');
    }

    function updateProgress(data) {
        const progressInsights = document.getElementById('progress-insights');

        if (data.chunk_summary) {
            const insight = document.createElement('div');
            insight.innerHTML = `
                <strong>Video ID:</strong> ${data.video_id}<br>
                <strong>Chunk:</strong> ${data.chunk_index} of ${data.total_chunks}<br>
                <strong>Summary:</strong> ${data.chunk_summary.full_summary || 'N/A'}<br>`;
            progressInsights.appendChild(insight);
        }
    }

    function displayCombinedSummary(data) {
        const combinedSummaryContent = document.getElementById('combined-summary-content');
        if (combinedSummaryContent) {
            combinedSummaryContent.innerHTML = `
                <h4>Full Summary</h4>
                <p>${data.full_summary}</p>
                <h4>Sections</h4>
                <ul>
                    ${data.sections.map(section => `
                        <li>
                            <strong>${section.title}</strong>: ${section.summary}
                            <br><small>${section.start_sentence}</small>
                        </li>`).join('')}
                </ul>
                <h4>Insights</h4>
                <ul>
                    ${data.insights.map(insight => `<li>${insight.text}</li>`).join('')}
                </ul>
                <h4>People</h4>
                <ul>
                    ${data.people.map(person => `<li>${person.name}</li>`).join('')}
                </ul>
                <h4>Primary Topics</h4>
                <ul>
                    ${data.primary_topics.map(topic => `<li>${topic}</li>`).join('')}
                </ul>`;
        }
    }

    function displayCrossVideoInsights(data) {
        const insightsContent = document.getElementById('cross-video-insights-content');
        if (insightsContent) {
            insightsContent.innerHTML = `
                <h4>Shared Insights</h4>
                <ul>
                    ${data.shared_insights.map(insight => `<li>${insight}</li>`).join('')}
                </ul>
                <h4>Common Themes</h4>
                <ul>
                    ${data.common_themes.map(theme => `<li>${theme}</li>`).join('')}
                </ul>
                <h4>Opposing Views</h4>
                <ul>
                    ${data.opposing_views.map(view => `<li>${view}</li>`).join('')}
                </ul>
                <h4>Sentiments</h4>
                <ul>
                    ${data.sentiments.map(sentiment => `<li>${sentiment}</li>`).join('')}
                </ul>`;
        }
    }

    function displayFinalResults(data) {
        const progressSection = document.getElementById('progress-section');
        const analysisResults = document.getElementById('analysis-results');

        progressSection.style.display = 'none';
        analysisResults.style.display = 'block';

        const combinedSummaryContent = document.getElementById('combined-summary-content');
        combinedSummaryContent.innerHTML = '';
        data.individual_results.forEach(result => {
            displayCombinedSummary(result);
        });

        displayCrossVideoInsights(data.cross_video_insights);
    }

    function displayAnswer(answer) {
        const answerContent = document.getElementById('answer-content');
        if (answerContent) {
            answerContent.innerHTML = `<p>${answer.answer}</p>`;
        }
    }

    function displayError(error) {
        const errorList = document.getElementById('error-list');
        if (errorList) {
            const li = document.createElement('li');
            li.classList.add('list-group-item', 'list-group-item-danger');
            li.innerText = `Error: ${error}`;
            errorList.appendChild(li);
        }
    }

    function showStatus(message, alertClass) {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.innerText = message;
            statusElement.className = `alert ${alertClass}`;
        }
    }

    const getVideosCategoryTextButton = document.getElementById('get-videos-category-text-button');
    if (getVideosCategoryTextButton) {
        getVideosCategoryTextButton.addEventListener('click', function () {
            const categoryIdInput = document.getElementById('category-id-text-input');
            const categoryId = categoryIdInput.value === "" ? null : categoryIdInput.value;
            const freeTextInput = document.getElementById('free-text-input');
            const freeText = freeTextInput.value === "" ? null : freeTextInput.value;
            sendMessage('get_videos', { categoryId, freeText });
        });
    } else {
        console.error('Search videos button not found');
    }

    const analyzeVideosButton = document.getElementById('analyze-videos-button');
    if (analyzeVideosButton) {
        analyzeVideosButton.addEventListener('click', function () {
            const videoIdsInput = document.getElementById('video-ids-input');
            if (videoIdsInput) {
                const selectedVideos = videoIdsInput.value.split(',').map(id => id.trim());
                startProgressBar(); // Start the progress bar animation immediately
                sendMessage('analyze_videos', { selectedVideos });
            } else {
                console.error('Video IDs input not found');
            }
        });
    } else {
        console.error('Analyze Videos button not found');
    }

    // Add this new function for toggling cards
    window.toggleCard = function (headerElement) {
        const card = headerElement.parentElement;
        const cardBody = card.querySelector('.card-body');
        const toggleIcon = card.querySelector('.toggle-icon');

        if (cardBody.style.display === 'none' || cardBody.style.display === '') {
            cardBody.style.display = 'block';
            toggleIcon.innerHTML = '&#9660;'; // Down arrow
        } else {
            cardBody.style.display = 'none';
            toggleIcon.innerHTML = '&#9654;'; // Right arrow
        }
    };

    // Add these new functions for expanding and collapsing cards
    function expandCard(card) {
        if (card) {
            const cardBody = card.querySelector('.card-body');
            const toggleIcon = card.querySelector('.toggle-icon');
            if (cardBody && toggleIcon) {
                cardBody.style.display = 'block';
                toggleIcon.innerHTML = '&#9660;'; // Down arrow
            }
        }
    }

    function collapseCard(card) {
        if (card) {
            const cardBody = card.querySelector('.card-body');
            const toggleIcon = card.querySelector('.toggle-icon');
            if (cardBody && toggleIcon) {
                cardBody.style.display = 'none';
                toggleIcon.innerHTML = '&#9654;'; // Right arrow
            }
        }
    }

    function collapseOtherCards(exceptCard) {
        const cards = document.querySelectorAll('.card');
        cards.forEach(card => {
            if (card !== exceptCard) {
                collapseCard(card);
            }
        });
    }
});

```

.chalice/config.json:

```
{
  "version": "2.0",
  "app_name": "video-exploratorium-backend",
  "automatic_layer": true,
  "stages": {
    "dev": {
      "api_gateway_stage": "vidbot",
      "lambda_memory_size": 1024,
      "lambda_timeout": 720,
      "manage_iam_role": false,
      "iam_role_arn": "arn:aws:iam::746027525716:role/ZoharTest-Lambda_Role",
      "environment_variables": {
        "SERVICE_URL": "https://cdnapi-ev.kaltura.com"
      },
      "lambda_functions": {
        "api_handler": {
          "architecture": "arm64"
        }
      },
      "tags": {
        "Environment": "dev",
        "Project": "VideoExploratorium"
      },
      "log_retention_in_days": 1,
      "api_gateway_endpoint_type": "EDGE",
      "timeout_settings": {
        "connect_timeout": 300,
        "read_timeout": 900
      },
      "websocket_api": {
        "route_selection_expression": "$request.body.action"
      }
    }
  }
}

```


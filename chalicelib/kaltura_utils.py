import re
import time
import json
import requests
import traceback
from lxml import etree
from KalturaClient import KalturaClient, KalturaConfiguration
from KalturaClient.Base import IKalturaLogger, KalturaParams, getXmlNodeFloat
from KalturaClient.exceptions import KalturaClientException, KalturaException
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
from chalicelib.utils import logger
from chalicelib.transcript_utils import chunk_transcript

class KalturaLogger(IKalturaLogger):
    def log(self, msg):
        logger.debug(msg)

class CustomKalturaClient(KalturaClient):
    def __init__(self, config, max_retries=1, delay=1, backoff=1):
        super().__init__(config)
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff

    def retry_on_exception(self, func, *args, **kwargs):
        mtries, mdelay = self.max_retries, self.delay
        while mtries > 1:
            try:
                return func(*args, **kwargs)
            except (KalturaException, KalturaClientException) as error:
                if self._is_non_retryable_error(error):
                    raise  # Raise the error without retrying if it's non-retryable
                msg = f"{str(error)}, Kaltura API retrying request in {mdelay} seconds..."
                context = f'Function "{func.__name__}" failed on attempt {self.max_retries - mtries + 1} with args {args} and kwargs {kwargs}.'
                self.log(f'retrying function due to error: {msg} Context: {context}')
                time.sleep(mdelay)
                mtries -= 1
                mdelay *= self.backoff
        return func(*args, **kwargs)  # retry one final time, if it fails again let the exception bubble up

    def _is_non_retryable_error(self, error):
        non_retryable_errors = ["INVALID_KS"]
        if isinstance(error, KalturaException) or isinstance(error, KalturaClientException):
            error_code = error.code
            return error_code in non_retryable_errors
        return False

    def parsePostResult(self, postResult):
        return self.retry_on_exception(self._parse_post_result, postResult)

    def _parse_post_result(self, postResult):
        try:
            postResult = re.sub(self.DATA_CONTENT_REGEX, b'<dataContent></dataContent>', postResult)
            self.log("removing dataContent tags to avoid utf8 decoding issues")
            self.log("result (xml): %s" % postResult)
            resultXml = etree.fromstring(postResult, parser=self.parser)
        except etree.ParseError as e:
            raise KalturaClientException(
                f"Failed to parse XML: {str(e)}",
                KalturaClientException.ERROR_INVALID_XML)

        resultNode = resultXml.find('result')
        if resultNode is None:
            raise KalturaClientException(
                'Could not find result node in response xml',
                KalturaClientException.ERROR_RESULT_NOT_FOUND)

        execTime = resultXml.find('executionTime')
        if (execTime is not None):
            self.executionTime = getXmlNodeFloat(execTime)

        self.throwExceptionIfError(resultNode)

        return resultNode

    def doHttpRequest(self, url, params=KalturaParams(), files=None):
        return self.retry_on_exception(super().doHttpRequest, url, params, files)

def get_kaltura_client(ks):
    config_kaltura = KalturaConfiguration()
    config_kaltura.serviceUrl = config.service_url
    config_kaltura.setLogger(KalturaLogger())
    client = CustomKalturaClient(config_kaltura, max_retries=1, delay=1, backoff=1)
    client.setKs(ks)
    return client

def validate_ks(ks):
    try:
        client = get_kaltura_client(ks)
        session_info: KalturaSessionInfo = client.session.get()
        is_ks_not_expired = session_info.expiry > time.time()
        masked_ks = f"{ks[:5]}...{ks[-5:]}"
        logger.debug(f"Validating Kaltura session: pid: {int(session_info.partnerId)}, ks_expiry_valid: {is_ks_not_expired} / masked_ks: {masked_ks}")
        pid = int(session_info.partnerId)
        return is_ks_not_expired, pid
    
    except Exception as e:
        masked_ks = f"{ks[:5]}...{ks[-5:]}"
        logger.error(f"Invalid Kaltura session (KS): {masked_ks}, Error: {e}")
        logger.error(traceback.format_exc())
        return False, -1

def get_english_captions(entry_id, ks, pid):
    client = get_kaltura_client(ks)
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

def fetch_videos(ks, pid, category_ids=None, free_text=None, number_of_videos=6):
    client = get_kaltura_client(ks)
    search_params = KalturaESearchEntryParams()
    search_params.orderBy = KalturaESearchOrderBy()
    order_item = KalturaESearchEntryOrderByItem()
    order_item.sortField = KalturaESearchEntryOrderByFieldName.CREATED_AT
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
    pager.pageSize = number_of_videos

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
        client = get_kaltura_client(ks)
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

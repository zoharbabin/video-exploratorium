import json
import traceback
from chalicelib.utils import logger, send_ws_message
from chalicelib.kaltura_utils import get_english_captions, get_json_transcript
from chalicelib.prompters import (generate_followup_questions_pp, analyze_chunk_pp,
                                  combine_chunk_analyses_pp, cross_video_insights_pp,
                                  VideoSummary, CrossVideoInsights, FollowupQuestionsResponse)


def analyze_videos_ws(app, connection_id, request_id, selected_videos, ks, pid):
    try:
        all_analysis_results = []
        all_transcripts = {}

        total_videos = len(selected_videos)

        for video_id in selected_videos:
            logger.info(f"Processing video ID: {video_id}")
            captions = get_english_captions(video_id, ks, pid)
            
            if captions:
                caption = captions[0]
                logger.info(f"Processing caption ID: {caption['id']} for video ID: {video_id}")
                segmented_transcript = get_json_transcript(caption['id'], ks, pid)
                logger.debug(f"Segmented transcript for caption ID {caption['id']}, total segments: {len(segmented_transcript)}")

                if not segmented_transcript:
                    logger.error(f"No caption content found for caption ID: {caption['id']}")
                    continue

                all_transcripts[video_id] = segmented_transcript

                chunk_summaries = []
                total_chunks = len(segmented_transcript)
                for index, segment in enumerate(segmented_transcript):
                    segment_text = json.dumps(segment)
                    logger.debug(f"Segment {index + 1}/{total_chunks} content for chunk analysis: {segment_text[:500]}...")
                    try:
                        chunk_summary: VideoSummary = analyze_chunk_pp(video_entry_id=video_id, chunk_transcript=segment_text)
                        chunk_json = chunk_summary.model_dump_json()
                        logger.info(f"Chunk {index + 1}/{total_chunks} analysis result: {chunk_json[:200]}...{chunk_json[-200:]}")
                        chunk_summaries.append(chunk_summary)
                        send_ws_message(app, connection_id, request_id, 'chunk_progress', {
                            'video_id': video_id,
                            'chunk_summary': chunk_json,
                            'chunk_index': index + 1,
                            'total_chunks': total_chunks,
                            'total_videos': total_videos
                        }, pid)
                    except Exception as e:
                        logger.error(f"Error during chunk analysis for video ID {video_id}, chunk {index + 1}: {e}")
                        logger.error(traceback.format_exc())

                if chunk_summaries:
                    try:
                        total_chunks = len(chunk_summaries)
                        if total_chunks > 1:
                            chunk_summaries_json = [summary.model_dump_json() for summary in chunk_summaries]
                            logger.info(f"Creating a combined analysis across chunks for video ID {video_id}")
                            combined_summary: VideoSummary = combine_chunk_analyses_pp(chunk_summaries=chunk_summaries_json)
                            combined_summary_dict = combined_summary.model_dump()
                            combined_summary_json = combined_summary.model_dump_json()
                            logger.info(f"Combined chunk analysis result for video ID {video_id}: {combined_summary_json[:500]}...{combined_summary_json[-500:]}")
                            all_analysis_results.append(combined_summary_dict)
                            send_ws_message(app, connection_id, request_id, 'combined_summary', combined_summary_json, pid)
                        else:
                            logger.info(f"Only one chunk found for video ID {video_id}, skipping combining analysis.")
                            combined_summary_dict = chunk_summaries[0].model_dump()
                            all_analysis_results.append(combined_summary_dict)
                            send_ws_message(app, connection_id, request_id, 'combined_summary', combined_summary_dict, pid)
                    except Exception as e:
                        logger.error(f"Error during combining chunk analyses for video ID {video_id}: {e}")
                        logger.error(traceback.format_exc())
                else:
                    logger.error(f"No chunk analysis results found for video ID {video_id}.")
        
        if not all_analysis_results:
            logger.error("No analysis results found.")
            send_ws_message(app, connection_id, request_id, 'error', 'No video transcript was found', pid)
            return

        response = {
            "individual_results": all_analysis_results,
            "transcripts": all_transcripts 
        }

        if len(selected_videos) > 1:
            try:
                logger.info(f"Creating videos analysis for {selected_videos}")
                full_summaries = [result["full_summary"] for result in all_analysis_results]
                cross_video_insights: CrossVideoInsights = cross_video_insights_pp(analysis_results=full_summaries)
                cross_video_insights_dict = cross_video_insights.model_dump()
                logger.debug(f"Cross video insights result: {cross_video_insights_dict}")
                response["cross_video_insights"] = cross_video_insights_dict
                send_ws_message(app, connection_id, request_id, 'cross_video_insights', cross_video_insights_dict, pid)
            except Exception as e:
                logger.error(f"Error during cross video insights analysis: {e}")
                logger.error(traceback.format_exc())

        logger.info("Video analysis complete")
        send_ws_message(app, connection_id, request_id, 'completed', response, pid)

    except Exception as e:
        logger.error(f"Error during video analysis: {e}")
        logger.error(traceback.format_exc())
        send_ws_message(app, connection_id, request_id, 'error', str(e), pid)


def generate_followup_questions_ws(app, connection_id, request_id, transcripts, pid):
    try:
        logger.info(f"Generating follow-up questions for analyzed videos.")
        transcripts_list = [json.dumps(segment) for segments in transcripts.values() for segment in segments]
        followup_questions_response: FollowupQuestionsResponse = generate_followup_questions_pp(transcripts=transcripts_list)
        followup_questions_dict = followup_questions_response.model_dump()
        logger.debug(f"Follow-up questions: {followup_questions_dict}")
        send_ws_message(app, connection_id, request_id, 'followup_questions', followup_questions_dict, pid)
    except Exception as e:
        logger.error(f"Error during generating follow-up questions: {e}")
        logger.error(traceback.format_exc())
        send_ws_message(app, connection_id, request_id, 'error', str(e), pid)

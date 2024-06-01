import json
import traceback
from chalicelib.kaltura_utils import get_english_captions, get_json_transcript
from chalicelib.prompters import analyze_chunk_pp, combine_chunk_analyses_pp, cross_video_insights_pp, VideoSummary, CrossVideoInsights
from chalicelib.utils import logger, send_ws_message

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
                segmented_transcripts = get_json_transcript(caption['id'], ks, pid)
                logger.debug(f"Segmented transcripts for caption ID {caption['id']}: {segmented_transcripts}")

                if not segmented_transcripts:
                    logger.error(f"No caption content found for caption ID: {caption['id']}")
                    continue

                # Collect the full transcript
                full_transcript = [entry for segment in segmented_transcripts for entry in segment['content']]
                all_transcripts[video_id] = full_transcript

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
                        send_ws_message(app, connection_id, request_id, 'chunk_progress', {
                            'video_id': video_id,
                            'chunk_summary': chunk_json,
                            'chunk_index': index + 1,
                            'total_chunks': total_chunks,
                            'total_videos': total_videos
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
                            send_ws_message(app, connection_id, request_id, 'combined_summary', combined_summary_json)
                        else:
                            logger.info(f"Only one chunk found for video ID {video_id}, skipping combining analysis.")
                            combined_summary_dict = chunk_summaries[0].model_dump()
                            all_analysis_results.append(combined_summary_dict)
                            send_ws_message(app, connection_id, request_id, 'combined_summary', combined_summary_dict)
                    except Exception as e:
                        logger.error(f"Error during combining chunk analyses for video ID {video_id}: {e}")
                        logger.error(traceback.format_exc())
                else:
                    logger.error(f"No chunk analysis results found for video ID {video_id}.")
        
        if not all_analysis_results:
            logger.error("No analysis results found.")
            send_ws_message(app, connection_id, request_id, 'error', 'No analysis results found')
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
                send_ws_message(app, connection_id, request_id, 'cross_video_insights', cross_video_insights_dict)
            except Exception as e:
                logger.error(f"Error during cross video insights analysis: {e}")
                logger.error(traceback.format_exc())

        logger.info("Video analysis complete")
        send_ws_message(app, connection_id, request_id, 'completed', response)

    except Exception as e:
        logger.error(f"Error during video analysis: {e}")
        logger.error(traceback.format_exc())
        send_ws_message(app, connection_id, request_id, 'error', str(e))

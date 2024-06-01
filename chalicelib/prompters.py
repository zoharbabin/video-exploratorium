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
    answer: str = Field(description="The answer to the user's question based on the provided videos context.")

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
        Below are summaries of one or multiple videos. 
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
def answer_question_pp(question: str, analysis_results: List[VideoSummary], transcripts: List[str], prior_chat_messages: List[str]) -> QAResponse:
    """
    - user:
        Below are summaries and transcripts of one or multiple videos, Chat history and the user's input question.
        Your task is to answer the user's question in a chatty way, based on the provided data.
        Be chatty and conversational in your response.
        

        ## Context
        
        ### Analysis Results:
        
        {{ analysis_results }}
        
        ### Videos Transcripts:

        {{ transcripts }}
        

        ## Chat History:

        {{ prior_chat_messages }}

        
        ## The Question You Should Answer:

        {{ question }}
        
    """

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

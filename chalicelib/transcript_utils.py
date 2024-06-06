import json

def chunk_transcript(data, max_chars=150000, overlap=10000):
    def get_json_size(segment):
        return len(json.dumps(segment))

    def add_segment(segments, segment):
        segments.append(segment)

    # Order the transcript by startTime in ascending order
    data.sort(key=lambda x: x['startTime'])

    segments = []
    current_segment = []
    text_buffer = ''
    
    # Chunk the transcript into segments
    for entry in data:
        for content in entry['content']:
            sentences = content['text'].split('\n')
            for sentence in sentences:
                if sentence:
                    sentence += '\n'
                    if not current_segment:
                        current_segment.append({'startTime': entry['startTime'], 'endTime': entry['endTime'], 'text': sentence.strip()})
                    else:
                        temp_segment = current_segment + [{'startTime': entry['startTime'], 'endTime': entry['endTime'], 'text': sentence.strip()}]
                        temp_size = get_json_size(temp_segment)
                        
                        if temp_size > max_chars:
                            add_segment(segments, current_segment)
                            overlap_text = text_buffer[-overlap:].strip()
                            current_segment = [{'startTime': entry['startTime'], 'endTime': entry['endTime'], 'text': overlap_text}]
                        else:
                            current_segment.append({'startTime': entry['startTime'], 'endTime': entry['endTime'], 'text': sentence.strip()})
                    
                    text_buffer += sentence
    
    if current_segment:
        add_segment(segments, current_segment)

    return segments
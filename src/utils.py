import yaml
import re
import sys
import threading
import queue
import os
import time
from initialize import obs_planner

def extract_valid_yaml(text):
    """Extract valid YAML content from text, including Markdown-formatted LLM responses."""
    try:
        # Match YAML content in Markdown code blocks or standard YAML formats
        patterns = [
            r'```yaml\n([\s\S]*?)```',       # Markdown YAML blocks
            r'(?:^|\n)(-{3}[\s\S]*?\.{3})',   # Standard YAML document markers
            r'(?:^|\n)(\{[\s\S]*?\})',        # JSON-style YAML
            r'(?:^|\n)([\w\s]*:[\s\S]*?)(?=\n\w+:|$)'  # Key-value pairs
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                try:
                    # Use group(1) to get content inside Markdown blocks or main capture group
                    content = match.group(1).strip()
                    parsed = yaml.safe_load(content)
                    if parsed:  # Ensure we got valid content
                        return parsed
                except yaml.YAMLError:
                    continue  # Skip invalid YAML blocks
                
        return None
        
    except Exception as e:
        print(f"Error extracting YAML: {e}")
        return None 


def stream_str(text):
    for word in text.split():
        yield word + " "
        time.sleep(0.01)


def stream_obs_planner_output(yaml_content):
    """
    Streams the output of the OBS planner to a generator.

    This function redirects the standard output to a queue and runs the OBS planner
    in a separate thread. The output is then yielded line by line until the planner
    completes its execution.

    Args:
        yaml_content (dict): The configuration dictionary to be passed to the OBS planner.

    Yields:
        str: Lines of output from the OBS planner.

    Example:
        for line in stream_obs_planner_output(config):
            print(line)
    """
def stream_obs_planner_output(yaml_content):
    output_queue = queue.Queue()
    
    class StreamToQueue:
        def __init__(self):
            self.queue = output_queue
        def write(self, message):
            # Queue each write operation, preserving original content
            if message:
                self.queue.put(message)
        def flush(self):
            if hasattr(self, 'buffer') and self.buffer:
                self.queue.put(self.buffer)
                self.buffer = ''

    old_stdout = sys.stdout
    sys.stdout = StreamToQueue()

    def run_obs_planner():
        try:
            obs_planner.main(config_dict=yaml_content)
        finally:
            sys.stdout.flush()  # Ensure any buffered content is flushed
            output_queue.put(None)  # Signal completion

    thread = threading.Thread(target=run_obs_planner)
    thread.start()

    buffer = ''
    
    while True:
        try:
            output = output_queue.get(timeout=1.0)  # Add timeout to prevent hanging
            if output is None:
                if buffer:  # Yield any remaining buffered content
                    yield buffer
                break
                
            buffer += output
            if '\n' in buffer:
                lines = buffer.split('\n')
                for line in lines[:-1]:
                    yield line + '\n'
                buffer = lines[-1]
                
        except queue.Empty:
            continue

    sys.stdout = old_stdout
    thread.join()
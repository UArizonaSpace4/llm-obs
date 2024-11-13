import yaml
import re
import sys
import threading
import queue
import os
import time
from initialize import obs_planner
import numpy as np

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


def stream_obs_planner_output(**kwargs):
    """
    Stream the output of obs_planner.main() with the given keyword arguments.
    All arguments are passed directly to obs_planner.main().
    """
    output_queue = queue.Queue()
    error_queue = queue.Queue()
    
    class StreamToQueue:
        def __init__(self):
            self.queue = output_queue
        def write(self, message):
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
            obs_planner.main(**kwargs)  # Pass all kwargs directly to main()
        except Exception as e:
            error_queue.put(e)
        finally:
            sys.stdout.flush()
            output_queue.put(None)

    thread = threading.Thread(target=run_obs_planner)
    thread.start()

    buffer = ''
    
    while True:
        try:
            # Check for exceptions first
            try:
                exc = error_queue.get_nowait()
                sys.stdout = old_stdout
                thread.join()
                raise exc  # Re-raise exception in main thread
            except queue.Empty:
                pass

            output = output_queue.get(timeout=1.0)
            if output is None:
                if buffer:
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

    # Check one final time for exceptions after thread completion
    try:
        exc = error_queue.get_nowait()
        raise exc
    except queue.Empty:
        pass


def read_tle_file(filename):
    tle_dict = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith('0'):
                # Skip the satellite name line
                tle_line1 = lines[i + 1].strip()
                tle_line2 = lines[i + 2].strip()
                # Extract NORAD ID from TLE line 1 (columns 3-7)
                norad_id = tle_line1[2:7].strip()
                tle_dict[norad_id] = (tle_line1, tle_line2)
                i += 3
            else:
                i += 1
    return tle_dict


def create_ground_track(satellite, t0, t1, ts, sat_name):
    # Generate 50 points between t0 and t1
    times = np.linspace(t0, t1, 50)
    times = ts.from_julian_date(times)
    
    # Calculate positions
    positions = satellite.at(times)
    lons, lats = positions.subpoint().longitude.degrees, positions.subpoint().latitude.degrees
    
    return {
        'lon': lons,
        'lat': lats,
        'name': sat_name
    }
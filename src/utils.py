import yaml
import re
import sys
import threading
import queue
import os

# Set up OBS_PLANNER_ROOT environment variable (must be absolute)
obs_planner_root = os.getenv("OBS_PLANNER_ROOT")
if not obs_planner_root or not os.path.isabs(obs_planner_root):
    raise ValueError("OBS_PLANNER_ROOT must be set to an absolute path")

# import the whole obs-planner module dynamically with importlib
import importlib.util
spec = importlib.util.spec_from_file_location("obs_planner", os.path.join(obs_planner_root, "obs_planner", "__init__.py"))
obs_planner = importlib.util.module_from_spec(spec)

def extract_valid_yaml(text):
    try:
        # Remove any surrounding text
        print(text)
        yaml_content = re.search(r'(?:^|\n)(-{3}.*?\.{3}|\{.*?\})', text, re.DOTALL)
        if yaml_content:
            return yaml.safe_load(yaml_content.group(0))
        return None
    except yaml.YAMLError:
        return None
        

def stream_obs_planner_output(yaml_content):
    output_queue = queue.Queue()

    class StreamToQueue:
        def __init__(self):
            self.queue = output_queue
            self.buffer = ''
        def write(self, message):
            if message != '\n':
                self.buffer += message
            else:
                self.queue.put(self.buffer)
                self.buffer = ''
        def flush(self):
            pass

    old_stdout = sys.stdout
    sys.stdout = StreamToQueue()

    def run_obs_planner():
        obs_planner.main(config_dict=yaml_content)
        output_queue.put(None)  # Signal completion

    thread = threading.Thread(target=run_obs_planner)
    thread.start()

    while True:
        output = output_queue.get()
        if output is None:
            break
        yield output

    sys.stdout = old_stdout
    thread.join()
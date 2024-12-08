import streamlit as st
import yaml
import re
import sys
import threading
import queue
import os
import time
from skyfield.api import load, EarthSatellite
import plotly.graph_objects as go 
from astropy.time import Time 
import pandas as pd
import datetime
import logging



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


def stream_function_output(func, **kwargs):
    """
    Stream the output of any function with the given keyword arguments.
    Args:
        func: The function to execute
        **kwargs: All arguments are passed directly to the function
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

    def run_function():
        try:
            func(**kwargs)  # Call the passed function with kwargs
        except Exception as e:
            error_queue.put(e)
        finally:
            sys.stdout.flush()
            output_queue.put(None)

    thread = threading.Thread(target=run_function)
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


def serialize_content(content, content_type):
    """
    Serializes message content based on its type.

    Args:
        content: The message content to serialize.
        content_type (str): The type of the content ('text', 'code', 'md', etc.).

    Returns:
        str: Serialized content as a string.
    """
    if content_type == "text" or content_type == "md":
        return str(content)
    elif content_type == "code":
        return f"```{content}```"
    elif isinstance(content, pd.DataFrame):
        return content.to_markdown()
    else:
        return str(content)
    

def format_date_for_filename(time_start: str) -> str:
    """
    Convert input time string to formatted date string for filename.
    
    Args:
        time_start: String containing date in format 'YYYY-MM-DD' or 'Now'
    
    Returns:
        String containing date formatted with underscores (YYYY_MM_DD)
    
    Raises:
        SystemExit: If date format is incorrect
    """
    obs_day = time_start.split(' ')[0]
    if obs_day == 'Now':
        obs_day = datetime.datetime.now().strftime('%Y-%m-%d')
    try:
        datetime.datetime.strptime(obs_day, '%Y-%m-%d')
    except ValueError:
        print("Incorrect data format, should be YYYY-MM-DD")
        sys.exit()
        
    date_local = obs_day + ' 17:30:00'
    date_utc = datetime.datetime.strptime(date_local, '%Y-%m-%d %H:%M:%S') + datetime.timedelta(hours=7)
    day_utc = date_utc.strftime('%Y-%m-%d')
    date_utc_with_underscore = day_utc.replace('-', '_')
    
    return date_utc_with_underscore


def display_message(msg, type: str = "text"):
    """Display a message in Streamlit with different formatting options.

    Args:
        msg: The message to display
        type: Format type - 'text', 'code', 'md', ...
    """
    if type == "code":
        st.code(msg)
    elif type == "md":
        st.markdown(msg)
    else:
        st.write(msg)  # Default to text for unknown types


def display_and_save(msg, type="text", role=None, append_to_last=True):
    """
        Write a message to the chat and save it to the session state.

        Args:
            msg: The message to write
            type: The type of message - 'text', 'code', 'md', or None (unspecified)
            role: The role of the speaker (user, assistant, status). If not provided, 
                    it will update the content of the last message appended
            append_to_last: If True and role is None, it will append the message to the last
                    message, as an array of strings (same with the type). If False, 
                    it will replace the content.
    """
    display_message(msg, type)
    if role:
        st.session_state.messages.append({"role": role, "type": [type], "content": [msg]})
    else:
        if append_to_last and "content" in st.session_state.messages[-1]:
            st.session_state.messages[-1]["content"].append(msg)
        else:
            st.session_state.messages[-1]["content"] = [msg]
        if append_to_last and "type" in st.session_state.messages[-1]:
            st.session_state.messages[-1]["type"].append(type)
        else:
            st.session_state.messages[-1]["type"] = [type]


def display_messages():
    """Function to display chat messages"""
    for message in st.session_state.messages:
        if message["role"] == "tool":
            with st.status(label=message["label"], state=message["state"]):
                if "content" in message:
                    if isinstance(message["content"], list):
                        for content in message["content"]:
                            display_message(content)
                    else:
                        display_message(message["content"])
        else:
            with st.chat_message(message["role"]):
                if isinstance(message["content"], list):
                    for content in message["content"]:
                        display_message(content)
                else:
                    display_message(message["content"])
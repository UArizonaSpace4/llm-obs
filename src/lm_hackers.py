##
## https://github.com/fastai/lm-hackers/blob/main/lm-hackers.ipynb
##
from fastcore.utils import nested_idx
import openai
from pydantic import create_model
import inspect, json
from inspect import Parameter
import os

import streamlit as st
import utils
from typing import List, Dict, Optional
import logging as log


openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

def response(compl): print(nested_idx(compl, 'choices', 0, 'message', 'content'))


def askgpt(user, system=None, model="gpt-4o", context=[], **kwargs):
    msgs = []
    if system: msgs.append({"role": "system", "content": system})
    if context and len(context) > 0: msgs += context
    msgs.append({"role": "user", "content": user})
    try:
        return client.chat.completions.create(model=model, messages=msgs, **kwargs)
    except Exception as e:
        log.error(f"Error in askgpt: {str(e)}")
        log.error(f"Messages that caused the error: {json.dumps(msgs, indent=2)}")
        raise e


def schema(f):
    kw = {n:(o.annotation, ... if o.default==Parameter.empty else o.default)
          for n,o in inspect.signature(f).parameters.items()}
    s = create_model(f'Input for `{f.__name__}`', **kw).schema()
    return dict(name=f.__name__, description=f.__doc__, parameters=s)


def prepare_context_messages(msgs: List[Dict[str, any]], n: Optional[int] = None, 
                             exclude_tool: bool = False, exclude_types: List[str] = []) -> List[Dict[str, any]]:
    """
    Prepares the last n messages from session state to send as context to the LLM.

    Args:
        msgs (List[dict]): List of messages to prepare.
        n (int, optional): Number of messages to include. If None, include all messages.
        exclude_tool (bool, optional): If True, filters out messages with role "tool".
        exclude_types (List[str], optional): List of message types to exclude.

    Returns:
        List[dict]: A list of serialized messages.
    """
    if n is not None:
        msgs = msgs[-n:]
    
    prepared_messages = []
    for message in msgs:
        if exclude_tool and message.get("role") == "tool":
            continue  # Skip messages with role "tool"
        
        prepared_message = {"role": message["role"], "content": ""}
        content = message.get("content", "")
        if "tool_calls" in message and not exclude_tool:
            prepared_message["tool_calls"] = message["tool_calls"]
        if "tool_call_id" in message:
            prepared_message["tool_call_id"] = message["tool_call_id"]

        if not isinstance(content, list): content = [content]
        serialized_items = []
        types = message.get("type", ["text"] * len(content))
        for item, item_type in zip(content, types):
            if item_type not in exclude_types:
                serialized_items.append(utils.serialize_content(item, item_type))
        prepared_message["content"] = "\n".join(serialized_items)

        prepared_messages.append(prepared_message)
    
    return prepared_messages


def handle_stream_response_tool_calls():
    """
    Processes chunks of a streaming response to extract tool call information.
    Returns:
        dict: A dictionary where each key is a tool call index and each value is a dictionary containing
              the tool call's id and function details (name and arguments).
    The function processes the last stream stored in session state, extracts tool call information, 
    and aggregates it into a dictionary.
    """
    tool_calls = {}

    for chunk in st.session_state["last_stream"]:
        delta = chunk.delta
        if delta.tool_calls:
            for tool_call in delta.tool_calls:
                if tool_call.index not in tool_calls:
                    tool_calls[tool_call.index] = {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": "",
                            "arguments": ""
                        }
                    }

                if tool_call.function.name:
                    tool_calls[tool_call.index]["function"]["name"] += tool_call.function.name
                if tool_call.function.arguments:
                    tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments

    # Convert dictionary to ordered list
    return [tool_calls[i] for i in sorted(tool_calls.keys())]
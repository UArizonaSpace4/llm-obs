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
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, BaseMessage, AIMessage, ToolCall
from collections import defaultdict


API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = os.getenv("LLM_API_BASE_URL")
MODEL = os.getenv("LLM_MODEL")
# client = openai.OpenAI(base_url=BASE_URL, api_key=API_KEY)


def response(compl): print(nested_idx(compl, 'choices', 0, 'message', 'content'))


def askgpt(user, system=None, model=MODEL, context=[], **kwargs):
    client = ChatOpenAI(model_name=model, base_url=BASE_URL, api_key=API_KEY)
    msgs = []
    if 'tools' in kwargs:
        client = client.bind_tools(kwargs['tools'])
    if system: msgs.append(SystemMessage(content=system))
    if context and len(context) > 0: msgs += context
    # msgs.append(HumanMessage(content=user))
    ret = client.stream(msgs)
    return ret


# def schema(f):
#     kw = {n:(o.annotation, ... if o.default==Parameter.empty else o.default)
#           for n,o in inspect.signature(f).parameters.items()}
#     s = create_model(f'Input for `{f.__name__}`', **kw).schema()
#     return dict(name=f.__name__, description=f.__doc__, parameters=s)


def prepare_context_messages(msgs: List[Dict[str, any] | BaseMessage], n: Optional[int] = None, 
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

    role_to_class = {
        "system": SystemMessage,
        "user": HumanMessage,
        "assistant": AIMessage,
        "tool": ToolMessage
    }
    
    prepared_messages = []
    for message in msgs:
        if exclude_tool and (isinstance(message, ToolMessage) or message.get("role") == "tool"):
            continue  # Skip messages with role "tool"
        
        prepared_message = {"role": message["role"], "content": ""}
        content = message.get("content", None)
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

        if message['role'] == 'tool':
            new_message = role_to_class[message["role"]](content=prepared_message['content'], tool_call_id=message["tool_call_id"])
        else:
            new_message = role_to_class[message["role"]](content=prepared_message['content'])
        if "tool_calls" in prepared_message:
            for tc in prepared_message["tool_calls"]:
                new_message.tool_calls.append(
                    ToolCall(id=tc['id'], name=tc['function']['name'], args=tc['function']['arguments'])
                )
        prepared_messages.append(new_message)
    
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
    tool_calls = defaultdict(list)

    for chunk in st.session_state["last_stream"]:
        if chunk.tool_call_chunks:
            for tool_call_chunk in chunk.tool_call_chunks:
                tool_calls[tool_call_chunk['index']].append(tool_call_chunk)

    merged_tool_calls = {}
    # Merge the tool call chunks
    for k, chunks in tool_calls.items():
       merged = {'index':k}
       for field in {'name', 'args', 'id'}:
           merged[field] = ''.join([chunk[field] for chunk in chunks if chunk[field]])
    merged = {
        "id": merged['id'],
        "function": {
            "name": merged['name'],
            "arguments": merged['args']
        }
    }
    merged_tool_calls[k] = merged

    # Convert dictionary to ordered list
    return [merged_tool_calls[i] for i in sorted(merged_tool_calls.keys())]
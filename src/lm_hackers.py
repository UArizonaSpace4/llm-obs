##
## https://github.com/fastai/lm-hackers/blob/main/lm-hackers.ipynb
##
from fastcore.utils import nested_idx
import openai
from pydantic import create_model
import inspect, json
from inspect import Parameter
import os
import utils

openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

def response(compl): print(nested_idx(compl, 'choices', 0, 'message', 'content'))


def askgpt(user, system=None, model="gpt-4o", context=[], **kwargs):
    msgs = []
    if system: msgs.append({"role": "system", "content": system})
    if context and len(context) > 0: msgs += context
    msgs.append({"role": "user", "content": user})
    return client.chat.completions.create(model=model, messages=msgs, **kwargs)


def schema(f):
    kw = {n:(o.annotation, ... if o.default==Parameter.empty else o.default)
          for n,o in inspect.signature(f).parameters.items()}
    s = create_model(f'Input for `{f.__name__}`', **kw).schema()
    return dict(name=f.__name__, description=f.__doc__, parameters=s)


def prepare_context_messages(msgs, n=None, exclude_tool=False):
    """
    Prepares the last n messages from session state to send as context to the LLM.

    Args:
        msgs (List[dict]): List of messages to prepare.
        n (int, optional): Number of messages to include. If None, include all messages.
        exclude_tool (bool, optional): If True, filters out messages with role "tool".

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

        if isinstance(content, list):
            serialized_items = []
            types = message.get("type", ["text"] * len(content))
            for item, item_type in zip(content, types):
                serialized_items.append(utils.serialize_content(item, item_type))
            prepared_message["content"] = "\n".join(serialized_items)
        else:
            content_type = message.get("type", "text")
            prepared_message["content"] = utils.serialize_content(content, content_type)

        prepared_messages.append(prepared_message)
    
    return prepared_messages
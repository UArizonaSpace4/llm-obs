import os
import openai
import streamlit as st
import time
import utils
import yaml
from initialize import obs_planner
from initialize import obs_tasker
import logging
import pandas as pd
from pathlib import Path
import sys
import json
from lm_hackers import response, askgpt, prepare_context_messages

# General config
is_mock = os.getenv("IS_MOCK", "False").lower() == "true"
project_root = Path(__file__).parent.parent.absolute()
tool_error = False

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()


#########################################################
### SESSION STATE INITIALIZATION AND HANDLERS
#########################################################

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

def update_selection():
    selected_indices = st.session_state.de["Select"]
    st.session_state.selected_passages = st.session_state.df[selected_indices]


def display_message(msg, type: str = "text"):
    """Display a message in Streamlit with different formatting options.
    
    Args:
        msg: The message to display
        type: Format type - 'text', 'code', or 'md'
    """
    if type == "text" or type is None:
        st.write(msg)
    elif type == "code":
        st.code(msg)
    elif type == "md":
        st.markdown(msg)
    else:
        st.text(msg)  # Default to text for unknown types


# Function to display chat messages
def display_messages():
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


def stream_response(compl, yield_in="content", sleep=0.01):
    """
    Streams the response from an API completion object and yields content incrementally.

    This function processes completion chunks, extracts specified content, and maintains
    a history of the stream in the session state. It can also simulate a streaming delay.

    Args:
        compl: The chat completion object with the response of the model
        yield_in (str): The attribute to extract from each chunk's delta (default: "content")
        sleep (float): Time in seconds to sleep between chunks for streaming effect (default: 0.01)

    Yields:
        str: Content extracted from each chunk based on the yield_in parameter

    Note:
        - Stores the stream history in st.session_state["last_stream"]
        - If sleep is truthy, adds a 0.01s delay between chunks
    """
    st.session_state["last_stream"] = []
    for chunk in compl:
        content = getattr(chunk.choices[0].delta, yield_in, "")
        if content is not None:
            yield content
        st.session_state["last_stream"].append(chunk.choices[0])
        if sleep: time.sleep(0.01)  # Simulate delay for streaming effect


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
                        "function": {
                            "name": "",
                            "arguments": ""
                        }
                    }
                
                if tool_call.function.name:
                    tool_calls[tool_call.index]["function"]["name"] += tool_call.function.name
                if tool_call.function.arguments:
                    tool_calls[tool_call.index]["function"]["arguments"] += tool_call.function.arguments
    
    return tool_calls


def process_tool_call(tool_call):
    """
    Process an OpenAI tool call object and extract relevant information.
    This function takes a tool call object and extracts its index, function name, and arguments.
    If the tool call is invalid or missing required attributes, returns None.
    Args:
        tool_call: An OpenAI tool call object containing function call information
    Returns:
        dict: A dictionary containing:
            - index (int): The index of the tool call
            - function_name (str): The name of the function being called
            - arguments (str): The arguments passed to the function
        None: If the tool call is invalid or missing required attributes
    Raises:
        AttributeError: If the tool call object is malformed or missing required attributes
    """
    try:
        if not tool_call or 'function' not in tool_call:
            return None
            
        return {
            "id": tool_call["id"],
            "function_name": tool_call["function"]["name"],
            "arguments": tool_call["function"]["arguments"]
        }
    except AttributeError as e:
        print(f"Error processing tool call: {e}")
        return None
    

def run_observation_planner(*config_parameters):
    """
    Run the observation planner tool with the provided arguments.
    This function takes a list of arguments, passes them to the observation planner tool,
    and returns the output.
    Args:
        *args: A list of arguments to pass to the observation planner tool
    Returns:
        Any: The output of the observation planner tool
    """
    global tool_error
    # Show a status container while the model is thinking
    with st.status("Running observation planner...", state="running") as status:
        st.session_state.messages.append({"role": "tool"})
        yaml_content = default_conf
        yaml_content.update(config_parameters)
    
        try:
            display_and_save("Default Configuration")
            display_and_save(yaml.dump(default_conf, sort_keys=False, default_flow_style=False), type="code")

            display_and_save("Your Configuration")
            display_and_save(yaml.dump(config_parameters, sort_keys=False, default_flow_style=False), type="code")

            display_and_save("Merged Configuration")
            display_and_save(yaml.dump(yaml_content, sort_keys=False, default_flow_style=False), type="code")

            if not is_mock:
                st.write_stream(utils.stream_function_output(obs_planner.main, config_dict=yaml_content,
                                                            txt_to_json=False))
            lbl = "Observation planner completed"
            state = "complete"
        except Exception as e:
            logging.exception(e)
            st.write(e)
            lbl = "Error running observation planner"
            state = "error"
            tool_error = True
        status.update(label=lbl, state=state)
        st.session_state.messages[-1].update({"label": lbl, "state": state})
    
    # Showing passages
    if not tool_error:
        if is_mock:
            passages_file = os.path.join(project_root, "mock_data", "2024_11_15__Passage_Galaxy.txt")
            tle_file = os.path.join(project_root, "mock_data", "2024_11_15__TLE_Galaxy.txt")
        else:
            passages_file = os.path.join(project_root, "mock_data", "2024_11_15__Passage_Galaxy.txt")
            tle_file = os.path.join(project_root, "mock_data", "2024_11_15__TLE_Galaxy.txt")

        with st.chat_message("assistant"):
            if passages_file and tle_file:
                passages = pd.read_csv(passages_file, comment='#', 
                                    sep='\s+', engine='python', header=None)
                headers = [
                    "ID", "name", "TLE epoch", "t0 [JD]", "az0 [deg]", "el0 [deg]", 
                    "t1 [JD]", "az1 [deg]", "el1 [deg]", "t2 [JD]", "az2 [deg]", "el2 [deg]", 
                    "exposures", "filter", "exp_time", "delay_after", "bin"
                ]
                passages.columns = headers
                passages['ID'] = passages['ID'].astype(str).str.zfill(5)
                tle_dict = utils.read_tle_file(tle_file)

                # Create a dataframe for display with fewer columns
                display_df = passages[['ID', 'name', 't0 [JD]', 't1 [JD]', 't2 [JD]', \
                                       'az0 [deg]', 'az1 [deg]', 'az2 [deg]', 'el0 [deg]', 
                                       'el1 [deg]', 'el2 [deg]']]

                display_and_save(display_df, role="assistant")

                fig = utils.plot_passages(passages, tle_dict)
                display_and_save(fig)

                # Call the LLM to explain the results
                kwargs = preset.copy()
                # No preset tools and context
                del kwargs['messages']; del kwargs['tools'] ; del kwargs['parallel_tool_calls']
                compl = askgpt(user = "The observation planner has finished. Answer the last user prompt",
                       system = system_prompt, 
                       context=prepare_context_messages(st.session_state.messages, n=None, exclude_tool=True),
                       stream=True,
                       **kwargs)
                st.write_stream(stream_response(compl))
    

def handle_tool_call(function_name, arguments):
    args_dict = json.loads(arguments)
    match function_name.lower():
        case "run_observation_planner":
            config_args = args_dict.get("config_args", [])
            config_dict = {}
            for param in config_args:
                name, value = param.split(":", 1)
                config_dict[name.strip()] = value.strip()
            run_observation_planner(**config_dict)
            
        case "query_database":
            # Run observation tasker
            pass
        case _:
            raise ValueError(f"Unknown function name: {function_name}")


def handle_user_prompt(prompt):   
    """
    Handles the prompt input by the user, interacts with the LLM to generate a response,
    processes the response to create a configuration, and runs the corresponding tool, if neccesasry.
    Args:
        prompt (str): The input prompt provided by the user.
    Returns:
        None
    Raises:
        Exception: If there is an error during the tool execution.
    """
    global tool_error
    response = client.chat.completions.create(
        model=preset["model"],
        messages= preset["messages"] + [{"role": "user", "content": prompt}],
        temperature=preset["temperature"],
        max_tokens=preset["max_tokens"],
        top_p=preset["top_p"],
        frequency_penalty=preset["frequency_penalty"],
        presence_penalty=preset["presence_penalty"],
        stream=True,
        tool_choice="auto",
        response_format={"type": "text"},
        parallel_tool_calls=False,
        tools=preset["tools"]
    )
    # Stream the response
    with st.chat_message("assistant"):       
        assistant_response = st.write_stream(stream_response(response))
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    if (st.session_state["last_stream"][-1].finish_reason == 'tool_calls'):
        tool_calls = handle_stream_response_tool_calls()
        try:
            tool_call = process_tool_call(tool_calls[0])
            if tool_call:
                handle_tool_call(tool_call["function_name"], tool_call["arguments"])
            else:
                display_and_save("Error processing tool call", role="assistant")        
        except Exception as e:
            logging.exception(e)
            st.write(e)
            tool_error = True
    else:
        logging.info("No tool found to call")


# If None, it takes the session state key from the chat input
def append_user_prompt(prompt: str = None):
    prompt = prompt or st.session_state.user_prompt
    st.session_state.messages.append({"role": "user", 
                                      "content": prompt})

######################################################################
# Streamlit app layout
######################################################################

# Read system prompt from file
with open("src/prompts/planner_configurator.md", "r") as file:
    system_prompt = file.read()

# Load default YAML configuration
default_conf_path = os.path.join(os.getenv("OBS_PLANNER_ROOT"), "configs", "config_default.yaml")
with open(default_conf_path, "r") as file:
    default_conf = yaml.safe_load(file)

# Load preset (default call configuration taken from the playground)
preset = {}
with open("src/prompts/preset.json", "r") as file:
    preset = json.load(file)
    preset.pop('system', None) # the system prompt is taken separately

st.set_page_config(layout="wide")
st.title("Observatory Chatbot")

if len(st.session_state.messages) == 0:
    # Display starter buttons
    starters = [
        "🛰️ Is there any LEO satellite visible in the next 48 hours with a magnitude greater than 17?",
        "📡 Can you schedule an observation of the INTELSAT satellites tomorrow tonight?"
    ]
    columns = st.columns(len(starters))
    for col, starter in zip(columns, starters):
        with col:
            st.button(starter, on_click=append_user_prompt, args=(starter,))
else:
    display_messages()
    messages = st.session_state.messages
    if messages[-1]["role"] == "user":
        handle_user_prompt(messages[-1]["content"])

# Chat input for user messages
st.chat_input("Type your message here...", key="user_prompt", 
              on_submit=append_user_prompt)

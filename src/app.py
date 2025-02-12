import sys
import os
import openai
import streamlit as st
import time
import planner
import utils
import yaml
from pathlib import Path
import logging
import pandas as pd
from pathlib import Path
import json
from lm_hackers import askgpt, handle_stream_response_tool_calls, prepare_context_messages
import random
from sqlalchemy import create_engine # for development
from db import Base
from utils import display_and_save
from utils import display_messages # for development
from streamlit.runtime.scriptrunner import get_script_run_ctx
from datetime import datetime
import weave

# General config
IS_DEV = os.getenv("IS_DEVELOPMENT", "True").lower() == "true"
IS_MOCK = os.getenv("IS_MOCK", "False").lower() == "true"
IS_DOCKER = os.getenv("IS_DOCKER", "False").lower() == "true"
STORE_CHATS = os.getenv("STORE_CHATS", "True").lower() == "true"
CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW", 4))
# Get database connection parameters from environment variables or use defaults
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'postgres')
DB_NAME = os.environ.get('DB_NAME', 'your_database_name')
EXCLUDE_TYPES= ["plot"] # types of messages to exclude from context

weave.init(os.getenv("WEAVE_PROJECT_NAME"))

ctx = get_script_run_ctx()
project_root = Path(__file__).parent.parent.absolute()
obs_planner_root = "/app/obs_planner" if IS_DOCKER else os.getenv("OBS_PLANNER_ROOT")
satpred_output_dir = os.getenv("SAT_PREDICTOR_OUTPUT_DIR")
current_datetime = datetime.now()
current_date = current_datetime.strftime("%Y-%m-%d")
current_time = current_datetime.strftime("%H:%M:%S")

# Import observation planner
sys.path.append(obs_planner_root)
import src as obs_planner # src refers to the src folder in the observation planner

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()


#########################################################
### SESSION STATE INITIALIZATION AND HANDLERS
#########################################################

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []


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


def run_observation_planner(config_parameters, st_status):
    """
    Run the observation planner tool with the provided arguments.
    This function takes a list of arguments, passes them to the observation planner tool,
    and returns the output.
    Args:
        *args: A list of arguments to pass to the observation planner tool
    Returns:
        Any: The output of the observation planner tool
    """
    tool_error = False
    # Show a status container while the model is thinking
    planner_conf = default_conf
    planner_conf["Criteria"].update(config_parameters)

    try:
        display_and_save("Parameters to update:")
        display_and_save(yaml.dump(config_parameters, sort_keys=False, default_flow_style=False), type="code")
        display_and_save("Configuration")
        display_and_save(yaml.dump(planner_conf, sort_keys=False, default_flow_style=False), type="code")

        if not IS_MOCK:
            st.write_stream(utils.stream_function_output(obs_planner.main, config_dict=planner_conf, txt_to_json=False, fill_with_defaults=False))
        lbl = "Observation planner completed"
        state = "complete"
    except Exception as e:
        logging.exception(e)
        st.write(e)
        lbl = "Error running observation planner"
        state = "error"
        tool_error = True
    st_status.update(label=lbl, state=state)
    st.session_state.messages[-1].update({"label": lbl, "state": state})
    return tool_error, planner_conf


def query_obs_db(psql, params=None):
    tool_error = False
    with st.status("Querying the database...", state="running") as status:
        try:
            res = obs_planner.database.push_to_db(
                credentials = db_credentials, 
                psql = psql,
                params = params)
            st.write(psql)
            st.write(params)
            display_and_save(res)
            lbl = "Query completed"
            state = "complete"
        except Exception as e:
            logging.exception(e)
            st.write(psql)
            st.write(params)
            display_and_save(e)
            lbl = "Error querying the database"
            state = "error"
            tool_error = True
        status.update(label=lbl, state=state)
        st.session_state.messages[-1].update({"label": lbl, "state": state})

    return tool_error
    

def handle_tool_call(function_name, arguments, tool_call_id):
    args_dict = json.loads(arguments)
    st.session_state.messages.append({"role": "tool", "tool_call_id": tool_call_id})
    match function_name.lower():
        case "run_observation_planner":
            with st.status("Running observation planner...", state="running") as status:
                config_args = args_dict.get("config_parameters", [])
                config_dict = {}
                for param in config_args:
                    name, value = param.split(":", 1)
                    config_dict[name.strip()] = utils.try_convert_number(value.strip())
                tool_error, planner_conf = run_observation_planner(config_dict, st_status=status)

            # Showing passages
            if not tool_error:
                if IS_MOCK:
                    passages_file = os.path.join(project_root, "mock_data", "2024_11_15__Passage_Galaxy.txt")
                    tle_file = os.path.join(project_root, "mock_data", "2024_11_15__TLE_Galaxy.txt")
                else:
                    date_utc_with_underscore = utils.format_date_for_filename(planner_conf['Criteria']['TimeStart'])
                    passages_file = os.path.join(satpred_output_dir, date_utc_with_underscore + "__Passage_" + UserData['username'] + '.txt')
                    tle_file = os.path.join(satpred_output_dir, date_utc_with_underscore + "__TLE_" + UserData['username'] + '.txt')

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
                        tle_dict = planner.read_tle_file(tle_file)

                        # Create a dataframe for display with fewer columns
                        display_df = passages[['ID', 'name', 't0 [JD]', 't1 [JD]', 't2 [JD]', \
                                            'az0 [deg]', 'az1 [deg]', 'az2 [deg]', 'el0 [deg]', 
                                            'el1 [deg]', 'el2 [deg]']]

                        display_and_save(display_df, role="assistant")

                        fig = planner.plot_passages(passages, tle_dict)
                        display_and_save(fig, type="plot")
            
        case "query_obs_db":
            # Query the database
            if "query" not in args_dict:
                st.write("Error calling the database. Query not found")
            else:
                tool_error = query_obs_db(psql=args_dict.get("query"), params=args_dict.get("params"))
        case _:
            raise ValueError(f"Unknown function name: {function_name}")
        
    # Call the LLM to explain the results (No preset tools)
    if not tool_error:
        kwargs = preset.copy(); del kwargs['tools'] 
        compl = askgpt(
            user = "Answer the last user prompt",
            system = system_prompt, 
            context=prepare_context_messages(st.session_state.messages, 
                                                n=None, exclude_tool=False,
                                                exclude_types=EXCLUDE_TYPES),
            stream=True,
            store=STORE_CHATS,
            metadata=dict(st_session_id=ctx.session_id),
            **kwargs)
        cntnt = st.write_stream(stream_response(compl))
        st.session_state.messages.append({"role": "assistant", "content": cntnt})


def handle_user_prompt(prompt, context_window=4):   
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
    kwargs = preset.copy()
    context = prepare_context_messages(msgs=demonstrations + st.session_state.messages, 
                                       n=context_window, exclude_tool=False, 
                                       exclude_types=EXCLUDE_TYPES)
    compl = askgpt(user = prompt, system = system_prompt, context=context, 
                   stream=True, tool_choice="auto", parallel_tool_calls=False, 
                   store=STORE_CHATS, 
                   metadata=dict(st_session_id=ctx.session_id), **kwargs)
    # Stream the response
    with st.chat_message("assistant"):       
        assistant_response = st.write_stream(stream_response(compl))
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

    if (st.session_state["last_stream"][-1].finish_reason == 'tool_calls'):
        tool_calls = handle_stream_response_tool_calls()
        st.session_state.messages[-1].update({"tool_calls": tool_calls})
        try:
            tool_call = tool_calls[0] # only first one
            if tool_call:
                handle_tool_call(tool_call["function"]["name"], 
                                 tool_call["function"]["arguments"],
                                 tool_call["id"])
            else:
                display_and_save("Error processing tool call", role="assistant")        
        except Exception as e:
            logging.exception(e)
            st.write(e)
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

# Create database, if needed and if we are in development
if IS_DEV:
    DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine, checkfirst=True)

# Load default YAML configuration
default_conf_path = os.path.join(obs_planner_root, "configs", "config_default.yaml")
with open(default_conf_path, "r") as file:
    default_conf = yaml.safe_load(file)

    UserData = {
            "organization" : default_conf['User']['UserUniqueId'], \
            "username": "llm", \
            "user_unique_id": default_conf['User']['UserUniqueId'], \
            "user_project": default_conf['User']['UserProject']
        }
    default_conf['User']['Username'] = "llm"

    db_credentials = {
        "ENDPOINT_reader": DB_HOST,
        "PORT" : 		DB_PORT,
        "USER" : 		DB_USER,
        "PASSWORD" : 	DB_PASSWORD,
        "DATABASE" :  "targets"
    }

# Load preset (default call configuration taken from the playground)
# https://platform.openai.com/playground/p/M4iHV1L0uG6MK5SwNMzfVi9E?mode=chat
with open("src/prompts/preset.json", "r") as file:
    preset = json.load(file)
    preset.pop('system', None) # the system prompt is taken separately
    preset.pop('messages', []) # the messages are taken separately

# Read system prompt (instructions) from file
with open("src/prompts/instructions.md", "r") as file:
    system_prompt = file.read()
    system_prompt = system_prompt.replace("{{CURRENT_DATE}}", current_date)
    system_prompt = system_prompt.replace("{{CURRENT_TIME}}", current_time) 
    system_prompt = system_prompt.replace("{{USERNAME}}", UserData["username"])

# Read demonstrations (few shot prompts) and add them as messages
with open("src/prompts/demonstrations.json", "r") as file:
    demonstrations = json.load(file)

# Load three random starters from the starters file
with open("src/prompts/starters.md", "r") as file:
    starters = file.readlines()
    starters = [starter.strip() for starter in starters if not starter.startswith('#') and starter.strip()]
    starters = random.sample(starters, 3)


st.set_page_config(layout="wide")
st.title("Space4 Chatbot")

if len(st.session_state.messages) == 0:
    # Display starter buttons
    columns = st.columns(len(starters))
    for col, starter in zip(columns, starters):
        with col:
            st.button(starter, on_click=append_user_prompt, args=(starter,))
else:
    display_messages()
    messages = st.session_state.messages
    if messages[-1]["role"] == "user":
        if len(messages) == 1:
            cwin = len(demonstrations)
        else:
            cwin = min(len(demonstrations) + len(messages), CONTEXT_WINDOW)
        handle_user_prompt(messages[-1]["content"], context_window=cwin)

# Chat input for user messages
st.chat_input("Type your message here...", key="user_prompt", 
              on_submit=append_user_prompt)

import os
import openai
import streamlit as st
import time
import utils
import yaml

# Set up OBS_PLANNER_ROOT environment variable (must be absolute)
obs_planner_root = os.getenv("OBS_PLANNER_ROOT")
if not obs_planner_root or not os.path.isabs(obs_planner_root):
    raise ValueError("OBS_PLANNER_ROOT must be set to an absolute path")

# Import the obs_planner module dynamically
import importlib.util
spec = importlib.util.spec_from_file_location("obs_planner", os.path.join(obs_planner_root, "obs_planner", "__init__.py"))
obs_planner = importlib.util.module_from_spec(spec)

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# Load default YAML configuration
default_conf_path = os.path.join(obs_planner_root, "configs", "GEOSurvey.yaml")
with open(default_conf_path, "r") as file:
    default_conf = yaml.safe_load(file)

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Function to display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Generator function to stream data
def stream_response(response_str):
    for chunk in response_str:
        content = chunk.choices[0].delta.content
        yield content
        time.sleep(0.02)  # Simulate delay for streaming effect

# Read system prompt from file
with open("src/system_prompt.md", "r") as file:
    system_prompt = file.read()


def prompt_handler(prompt):   
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt) 

    # Show a status container while the model is thinking
    with st.status("Creating configuration...", state="running") as status:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=2048,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stream=True
        )
        # Stream the response
        assistant_response = st.write_stream(stream_response(response))
        st.session_state.messages.append({"role": "assistant", "content": assistant_response[0]})

        # Extract YAML content
        yaml_content = utils.extract_valid_yaml(assistant_response[0])

        if yaml_content:
            status.update(label="Configuration created", state="complete")
            st.write_stream(stream_response(yaml_content))
            with status("Running observation planner...", state="running"):
                # Merge configurations and run the planner
                yaml_content = {**default_conf, **yaml_content}
                obs_planner.main(config_dict=yaml_content)
        else:
            status.update(label="Error", state="error")

# Function to process the last user message
def process_new_messages():
    messages = st.session_state.messages
    for message in reversed(messages):
        if message["role"] == "user":
            prompt_handler(message["content"])
            break

# If None, it takes the session state key from the chat input
def append_user_prompt(prompt: str = None):
    print("USER PROMPT")
    prompt = prompt or st.session_state.user_prompt
    st.session_state.messages.append({"role": "user", 
                                      "content": prompt})

######################################################################
# Streamlit app layout
######################################################################

st.title("Observatory Chatbot")
print(f'Length of messages: {len(st.session_state.messages)}')
print(f'Messages: {st.session_state.messages}')

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
    # TODO:display?
    process_new_messages()

# Chat input for user messages
st.chat_input("Type your message here...", key="user_prompt", 
              on_submit=append_user_prompt)

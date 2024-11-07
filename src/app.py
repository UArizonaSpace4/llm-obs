import os
import openai
import streamlit as st
import time
import utils
import yaml
import sys
import importlib.util
from initialize import obs_planner

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# Load default YAML configuration
default_conf_path = os.path.join(os.getenv("OBS_PLANNER_ROOT"), "configs", "GEOSurvey.yaml")
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
def stream_response(response):
    for chunk in response:
        content = chunk.choices[0].delta.content
        yield content
        time.sleep(0.01)  # Simulate delay for streaming effect


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
        st.session_state.messages.append({"role": "thinking", "content": assistant_response[0]})

        # Extract YAML content
        yaml_content = utils.extract_valid_yaml(assistant_response[0])
        if yaml_content:
            status.update(label="Configuration created", state="complete")
            msg = "Configuration created successfully."
        else:
            status.update(label="Error", state="error")
            msg = "Sorry, I couldn't extract a valid configuration. Please try again."

    st.session_state.messages.append({"role": "assistant", "content": msg})
    with st.chat_message("assistant"):
        st.markdown(msg)
    
    with st.status("Running observation planner...", state="running") as status:
        # Merge configurations and run the planner
        yaml_content = {**default_conf, **yaml_content}
        print(yaml_content)
        st.write_stream(utils.stream_obs_planner_output(yaml_content))
        status.update(label="Observation planner completed", state="complete")
    




# Function to process the last user message
def process_last_user_msg():
    messages = st.session_state.messages
    if messages[-1]["role"] == "user":
        prompt_handler(messages[-1]["content"])

# If None, it takes the session state key from the chat input
def append_user_prompt(prompt: str = None):
    prompt = prompt or st.session_state.user_prompt
    st.session_state.messages.append({"role": "user", 
                                      "content": prompt})

######################################################################
# Streamlit app layout
######################################################################

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
    # TODO:display?
    process_last_user_msg()

# Chat input for user messages
st.chat_input("Type your message here...", key="user_prompt", 
              on_submit=append_user_prompt)

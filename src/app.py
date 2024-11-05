import os
import openai
import streamlit as st
import time
from utils import extract_valid_yaml


# Add title and description to the app
st.title("Observatory Chatbot")

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# Initialize session state for messages if not already done
if "messages" not in st.session_state:
    st.session_state.messages = []

# Function to display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Read system prompt from file
with open("src/system_prompt.md", "r") as file:
    system_prompt = file.read()

# Display existing chat messages
display_messages()

# Generator function to stream data
def stream_response(response_str):
    for chunk in response_str:
        content = chunk.choices[0].delta.content
        yield content
        time.sleep(0.02)  # Simulate delay for streaming effect

# Chat input for user to type messages
if prompt := st.chat_input("Type your message here..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Show a status container while the model is thinking
    with st.status("Creating configuration...", state="running") as status:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=1,
            max_tokens=2048,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stream=True  # Enable streaming
        )
        # Stream the response using st.write_stream
        assistant_response = st.write_stream(stream_response(response))
        # TODO:Should this be saved even if they are not visible tokens?
        st.session_state.messages.append({"role": "assistant", "content": assistant_response})

        # Extract YAML content from the assistant response
        yaml_content = extract_valid_yaml(assistant_response)

        if yaml_content:
            status.update(label="Configuration created", state="complete")
            st.write_stream(stream_response(yaml_content))
        else:
            status.update(label="Error", state="error")
            
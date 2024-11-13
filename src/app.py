import os
import openai
import streamlit as st
import time
import utils
import yaml
from initialize import obs_planner
import logging #TODO: Add to requirements
import pandas as pd #TODO: Add to requirements
from skyfield.api import load, EarthSatellite #TODO: Add to requirements
import plotly.graph_objects as go #TODO: Add to requirements
from astropy.time import Time # TODO:Add to requirements

# General config
is_mock = os.getenv("IS_MOCK", False)

# Set up OpenAI API credentials
openai.api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# Load default YAML configuration
default_conf_path = os.path.join(os.getenv("OBS_PLANNER_ROOT"), "configs", "config_default.yaml")
with open(default_conf_path, "r") as file:
    default_conf = yaml.safe_load(file)


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


def display_and_save(msg, type="text", role=None, append_to_last=True):
    """"
        Write a message to the chat and save it to the session state.

        Args:
            msg: The message to write
            type: The type of message - 'text', 'code', or 'md'
            role: The role of the speaker (user, assistant, status). If not provided, 
            it will update the content of the last message appended
            append_to_last: If True and role is None, it will append the message to the last
            message, as an array of strings (same with the type). If False, it will replace the content.
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

# Function to display chat messages
def display_messages():
    for message in st.session_state.messages:
        if message["role"] == "status":
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
    # Show a status container while the model is thinking
    with st.status("Creating configuration...", state="running") as status:
        st.session_state.messages.append({"role": "status"})
        if is_mock:
            # Use default config for mockup
            yaml_content = default_conf
        else:
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
            st.session_state.messages[-1].update({"content": assistant_response[0]})

        if yaml_content:
            lbl = "Configuration created"
            state = "complete"
            msg = "Configuration created successfully. I'll proceed to run the observation planner."
        else:
            lbl = "Error creating configuration"
            state = "error"
            msg = "Sorry, I couldn't extract a valid configuration. Please try again."
        status.update(label=lbl, state=state)
        st.session_state.messages[-1].update({"label": lbl, "state": state})

    # Display assistant message
    with st.chat_message("assistant"):
        display_and_save(msg, role="assistant")
        #st.markdown(msg)
        #st.session_state.messages.append({"role": "assistant", "content": msg})
    
    with st.status("Running observation planner...", state="running") as status:
        st.session_state.messages.append({"role": "status", "content": []})
        try:
            display_and_save("Default Configuration")
            display_and_save(yaml.dump(default_conf, sort_keys=False, default_flow_style=False), type="code")

            display_and_save("Your Configuration")
            display_and_save(yaml.dump(yaml_content, sort_keys=False, default_flow_style=False), type="code")

            # Merge configurations
            yaml_content = {**default_conf, **yaml_content}

            display_and_save("Merged Configuration")
            display_and_save(yaml.dump(yaml_content, sort_keys=False, default_flow_style=False), type="code")

            if not is_mock:
                st.write_stream(utils.stream_obs_planner_output(config_dict=yaml_content,
                                                            txt_to_json=False))
            lbl = "Observation planner completed"
            state = "complete"
        except Exception as e:
            logging.exception(e)
            lbl = "Error running observation planner"
            state = "error"
        status.update(label=lbl, state=state)
        st.session_state.messages[-1].update({"label": lbl, "state": state})
    
    # Showing passages
    passages_file = os.path.join(os.getenv("OBS_PLANNER_ROOT"), "examples", "2024_08_28__Passage_Galaxy.txt")
    tle_file = os.path.join(os.getenv("OBS_PLANNER_ROOT"), "examples", "2024_08_28__TLE_GEO.txt")

    with st.chat_message("assistant"):
        if passages_file and tle_file:
            passages = pd.read_csv(passages_file, comment='#', 
                                   sep='\s+', engine='python', header=None)
            headers = [
                "ID", "name", "epoch", "t0 [MJD]", "az0 [deg]", "el0 [deg]", 
                "t1 [MJD]", "az1 [deg]", "el1 [deg]", "t2 [MJD]", "az2 [deg]", "el2 [deg]", 
                "exposures", "filter", "exp_time", "delay_after", "bin"
            ]
            passages.columns = headers
            passages['ID'] = passages['ID'].astype(str).str.zfill(5)
            tle_dict = utils.read_tle_file(tle_file)

            print(f"Passage IDs: {passages['ID'].unique()}")
            print(f"TLE IDs: {list(tle_dict.keys())}")
            # Create a dataframe for display with fewer columns
            display_df = passages[['ID', 'name', 't0 [MJD]', 't1 [MJD]', 'az0 [deg]', \
                                   'el0 [deg]']]

            # Allow multiple selection of rows
            st.dataframe(display_df,hide_index=True,use_container_width=True)

            # Create the map
            fig = go.Figure()
            
            # Add base map
            fig.add_trace(go.Scattergeo(
                showlegend=False,
                mode='lines',
                line=dict(width=1, color='gray'),
            ))
            
            # Time scale 
            ts = load.timescale()

            for _, sat_row in passages.iterrows():
                sat_id = sat_row['ID']
                sat_name = sat_row['name']
                print(f"Processing satellite ID: {sat_id}, Name: {sat_name}")
                
                if sat_id in tle_dict:
                    # Get satellite TLE
                    print(f"Satellite {sat_name} found in TLE dictionary.")
                    tle_lines = tle_dict[sat_id]
                    satellite = EarthSatellite(tle_lines[0], tle_lines[1], sat_name, ts)
                    
                    # Calculate positions (e.g. 100 points between t0 and t2)
                    t0 = Time(sat_row['t0 [MJD]'], format='mjd').datetime
                    t2 = Time(sat_row['t2 [MJD]'], format='mjd').datetime
                    times = pd.date_range(start=t0, end=t2, periods=100)
                    
                    # Convert times to positions
                    positions = []
                    for t in times:
                        t_ts = ts.from_datetime(t)
                        geocentric = satellite.at(t_ts)
                        subpoint = geocentric.subpoint()
                        positions.append((subpoint.longitude.degrees, 
                                        subpoint.latitude.degrees))
                    
                    # Add trajectory to map
                    lons, lats = zip(*positions)
                    fig.add_trace(go.Scattergeo(
                        lon=lons,
                        lat=lats,
                        mode='lines',
                        name=sat_name,
                        line=dict(width=2),
                        legendgroup=sat_name,
                        showlegend=True,
                        customdata=[[sat_id, sat_row['t0 [MJD]'], sat_row['t1 [MJD]']]] * len(lons),
                        hovertemplate=(
                            "<b>%{name}</b><br>" +
                            "ID: %{customdata[0]}<br>" +
                            "Start: %{customdata[1]:.2f} MJD<br>" +
                            "End: %{customdata[2]:.2f} MJD<br>" +
                            "<extra></extra>"
                        )
                    ))
                else:
                    print(f"Satellite {sat_name} not found in TLE dictionary.")
            
            # # Update layout
            fig.update_layout(
                showlegend=True,
                geo=dict(
                    showland=True,
                    showcountries=True,
                    showocean=True,
                    countrywidth=0.5,
                    landcolor='rgb(243, 243, 243)',
                    oceancolor='rgb(204, 229, 255)',
                    projection_type='equirectangular',
                ),
                height=600,
            )
                
            # Display the map
            st.plotly_chart(fig, use_container_width=True)



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
    display_messages()
    process_last_user_msg()

# Chat input for user messages
st.chat_input("Type your message here...", key="user_prompt", 
              on_submit=append_user_prompt)

import yaml
import re
import sys
import threading
import queue
import os
import time
import numpy as np
from skyfield.api import load, EarthSatellite
import plotly.graph_objects as go 
from astropy.time import Time 
import numpy as np
import pandas as pd


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


def read_tle_file(filename):
    tle_dict = {}
    with open(filename, 'r') as f:
        lines = f.readlines()
        i = 0
        while i < len(lines):
            if lines[i].startswith('0'):
                # Skip the satellite name line
                tle_line1 = lines[i + 1].strip()
                tle_line2 = lines[i + 2].strip()
                # Extract NORAD ID from TLE line 1 (columns 3-7)
                norad_id = tle_line1[2:7].strip()
                tle_dict[norad_id] = (tle_line1, tle_line2)
                i += 3
            else:
                i += 1
    return tle_dict


def create_ground_track(satellite, t0, t1, ts, sat_name):
    # Generate 50 points between t0 and t1
    times = np.linspace(t0, t1, 50)
    times = ts.from_julian_date(times)
    
    # Calculate positions
    positions = satellite.at(times)
    lons, lats = positions.subpoint().longitude.degrees, positions.subpoint().latitude.degrees
    
    return {
        'lon': lons,
        'lat': lats,
        'name': sat_name
    }

def plot_passages(passages_df, tle_dict):
    """Plot satellite passages on an interactive map."""
    import plotly.graph_objects as go
    import numpy as np
    from skyfield.api import load, EarthSatellite

    fig = go.Figure()

    # Add geostationary belt visualization
    belt_lons = np.linspace(-180, 180, 360)
    belt_lats = np.zeros_like(belt_lons)

    fig.add_trace(go.Scattergeo(
        lon=belt_lons,
        lat=belt_lats,
        mode='lines',
        name='GEO Belt',
        line=dict(
            color='rgba(100,100,100,0.8)',
            width=2,
            dash='dash'
        ),
        showlegend=True
    ))

    ts = load.timescale()

    # Plot each satellite
    for _, sat_row in passages_df.iterrows():
        sat_id = sat_row['ID']
        sat_name = sat_row['name']

        if sat_id in tle_dict:
            tle_lines = tle_dict[sat_id]
            satellite = EarthSatellite(tle_lines[0], tle_lines[1], sat_name, ts)

            t = ts.tt_jd(float(sat_row['t0 [JD]']))
            geocentric = satellite.at(t)
            subpoint = geocentric.subpoint()

            fig.add_trace(go.Scattergeo(
                lon=[subpoint.longitude.degrees],
                lat=[subpoint.latitude.degrees],
                mode='markers+text',
                name=sat_name,
                marker=dict(
                    size=10,
                    symbol='diamond',
                    line=dict(
                        width=1,
                        color='white'
                    )
                ),
                text=[sat_name],
                textposition="top center",
                textfont=dict(
                    size=14,
                    color='black'
                ),
                hovertemplate=(
                    "<b>%{text}</b><br>" +
                    "Longitude: %{lon:.2f}°<br>" +
                    "Latitude: %{lat:.2f}°<br>" +
                    "<extra></extra>"
                ),
                showlegend=True
            ))

    # Add Tucson marker
    fig.add_trace(go.Scattergeo(
        lon=[-110.9747],
        lat=[32.2226],
        mode='markers+text',
        name='Tucson',
        marker=dict(
            size=12,
            symbol='star',
            color='red',
            line=dict(
                width=1,
                color='black'
            )
        ),
        text=['Tucson'],
        textposition="top center",
        showlegend=True,
        hovertemplate="<b>Tucson Observatory</b><br>" +
                     "Lat: 32.2226°N<br>" +
                     "Lon: 110.9747°W<br>" +
                     "<extra></extra>"
    ))

    # Update layout
    fig.update_layout(
        title=dict(
            text="Geostationary Satellite Positions",
            y=0.95,
            x=0.5,
            xanchor='center',
            yanchor='top',
            font=dict(size=20)
        ),
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.9,
            xanchor="right",
            x=0.99,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='rgba(0,0,0,0.2)',
            borderwidth=1
        ),
        geo=dict(
            projection_type='equirectangular',
            center=dict(lon=-110.9747, lat=32.2226),  # Tucson coordinates
            showland=True,
            showcountries=True,
            showocean=True,
            landcolor='rgb(243, 243, 243)',
            oceancolor='rgb(204, 229, 255)',
            lataxis=dict(
                range=[-30, 90],   # Adjusted to show more of North America
                dtick=30
            ),
            lonaxis=dict(
                range=[-180, 180],
                dtick=60
            ),
            domain=dict(
                x=[0, 1],  # Full width
                y=[0, 1]   # Full height
            ),
            bgcolor='rgba(255,255,255,0)',
            showcoastlines=True,
            coastlinecolor='rgb(100,100,100)',
            showframe=False,
            #fitbounds="locations",  # Ensure the map fits the data
            scope='world',  # Ensure world map is loaded
            projection_scale=2,  # Initial zoom level
        ),
        height=600,  # Adjust as needed
        margin=dict(l=10, r=10, t=50, b=10),  # Minimal margins
        paper_bgcolor='white',
        plot_bgcolor='white'
    )

    return fig


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
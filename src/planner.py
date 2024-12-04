import plotly.graph_objects as go
import numpy as np
from skyfield.api import load, EarthSatellite

def plot_passages(passages_df, tle_dict):
    """Plot satellite passages on an interactive map."""

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
            text="Satellite Positions",
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
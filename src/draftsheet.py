from skyfield.api import load, EarthSatellite
from sgp4.earth_gravity import wgs84
from datetime import datetime, timedelta

# Load TLE data
line1 = "1 25544U 98067A   24100.50000000  .00000000  00000+0  00000+0 0  9999"
line2 = "2 25544  51.6400 180.0000 0000000   0.0000   0.0000 15.50000000    00"

# Create satellite object
satellite = EarthSatellite(line1, line2)
ts = load.timescale()

# Generate time points
times = ts.utc(2024, 4, [14, 15])  # Example date range

# Calculate positions
positions = satellite.at(times)

# For ground track plotting
from cartopy import crs as ccrs
import matplotlib.pyplot as plt

# Create map
plt.figure(figsize=(15, 10))
ax = plt.axes(projection=ccrs.PlateCarree())
ax.coastlines()

# Plot satellite ground track
lons, lats = positions.subpoint().longitude.degrees, positions.subpoint().latitude.degrees
ax.plot(lons, lats, 'r-', transform=ccrs.PlateCarree())
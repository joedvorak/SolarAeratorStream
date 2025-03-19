import numpy as np
import streamlit as st
import json
import PySAM.Pvsamv1 as pv
import PySAM.ResourceTools as tools
import folium
from streamlit_folium import st_folium
import pandas as pd
import os
import glob
import re

st.set_page_config(
    page_title="Solar Aeration Energy Estimator",
    page_icon=":material/sunny:",
    layout="wide",
)
st.title("Solar Aeration Energy Estimator")

# Constants
json_file_2_panel = "./2-Panel_pvsamv1.json"
json_file_4_panel = "./4-Panel_pvsamv1.json"
sam_api_key = st.secrets['NSRDB_API_KEY']
sam_email = st.secrets['NSRDB_API_EMAIL']
temp_res_dir = 'solar_data/'
MAX_FILES = 10  # Maximum number of files to keep

# Initialize session state
if 'energy_output' not in st.session_state:
    st.session_state['energy_output'] = None
if 'processing' not in st.session_state:
    st.session_state['processing'] = False
if 'latitude' not in st.session_state:
    st.session_state['latitude'] = 38.0367
if 'longitude' not in st.session_state:
    st.session_state['longitude'] = -84.5078
if 'map_center' not in st.session_state:
    st.session_state['map_center'] = [38.0367, -84.5078]  # Default: Lexington, KY
if 'selected_aerator' not in st.session_state:
    st.session_state['selected_aerator'] = "2-Panel"  # Default aerator
if 'tilt' not in st.session_state:
    st.session_state['tilt'] = 15 # Default tilt


st.write("Select a location on the map to see the output from the solar aerator.")

# Add aerator type selection
aerator_type = st.selectbox(
    "Select Aerator Type",
    ["2-Panel", "4-Panel"],
    index=0,  # Default to 2-Panel
    key="aerator_type_selectbox" # Add a key
)
st.session_state['selected_aerator'] = aerator_type # Store selection

# Add tilt input
tilt = st.number_input("Enter Tilt Angle (degrees)", value=st.session_state['tilt'], min_value=0, max_value=90, key="tilt_input")
st.session_state['tilt'] = tilt # Store tilt

# Create a map using folium
m = folium.Map(location=st.session_state['map_center'], zoom_start=5)

# Function to extract lat/lon from filename
def extract_lat_lon(filename):
    match = re.search(r"nsrdb_(-?\d+\.\d+)_(-?\d+\.\d+)_", filename)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

# Add markers for existing files
csv_files = glob.glob(os.path.join(temp_res_dir, "*_psm3-tmy_*.csv"))
for csv_file in csv_files:
    lat, lon = extract_lat_lon(os.path.basename(csv_file))
    if lat is not None and lon is not None:
        folium.Marker(
            location=[lat, lon],
            popup=f"Existing Data: Lat={lat}, Lon={lon}",
            icon=folium.Icon(color='green')  # Use a different color for existing data
        ).add_to(m)

folium.Marker(
        location=[st.session_state['latitude'], st.session_state['longitude']],
        popup=f"Selected Location: Lat={st.session_state['latitude']}, Lon={st.session_state['longitude']}",
        icon=folium.Icon(color='blue')  # Use a different color for the selected location
).add_to(m)


# Display the map in Streamlit
map_data = st_folium(m, width=800, height=600)

# Get the selected coordinates from the map
if map_data and map_data["last_clicked"]:
    st.session_state['latitude'] = round(map_data["last_clicked"]["lat"], 4)
    st.session_state['longitude'] = round(map_data["last_clicked"]["lng"], 4)

# Display the selected coordinates
st.write(f"Selected Latitude: {st.session_state['latitude']}")
st.write(f"Selected Longitude: {st.session_state['longitude']}")


if st.button("Calculate Energy Output"):  # Wrap the calculation in a button
    st.session_state['processing'] = True

if st.session_state['processing']:

    # Clear previous energy output
    st.session_state['energy_output'] = None      
    # Use st.status to show progress
    with st.status("Downloading Solar Resource Data if necessary...", state="running") as status:
        nsrdbfetcher = tools.FetchResourceFiles(
            tech='solar',
            nrel_api_key=sam_api_key,
            nrel_api_email=sam_email,  # Do not use tmy for durability analysis
            resource_dir=temp_res_dir,
            resource_type='psm3-tmy',
            verbose=True,
        )
        lon_lats = [(st.session_state['longitude'], st.session_state['latitude'])] # Use values from session state
        nsrdbfetcher.fetch(lon_lats)
        nsrdb_path_dict = nsrdbfetcher.resource_file_paths_dict
        nsrdb_fp = nsrdb_path_dict[lon_lats[0]]
        # The file path is a text string of the resource_dir/file_name
        # To remove the resource_dir
        base_filename = nsrdb_fp.replace(temp_res_dir, "")
        print(f"nsrdb_fp {nsrdb_fp}")
        print(f"base_filename {base_filename}")
        status.update(label="Solar Resource Data Ready!", state="complete")

        # File management
    with st.status("Maximum location count exceeded. Removing oldest locations...", state="running") as status:
        all_files = glob.glob(os.path.join(temp_res_dir, "*"))  # Get all files in the directory
        if len(all_files) > MAX_FILES:
            # Sort files by modification time (oldest first)
            sorted_files = sorted(all_files, key=os.path.getmtime)
            files_to_remove = sorted_files[:len(all_files) - MAX_FILES]  # Get the oldest files to remove
            for file_path in files_to_remove:
                try:
                    os.remove(file_path)
                    print(f"Removed old file: {file_path}")
                except Exception as e:
                    print(f"Error removing file {file_path}: {e}")
        status.update(label="Old Solar Resource Data Files Removed!", state="complete")

    with st.status("Calculating Energy Output...", state="running") as status:
        pv_model = pv.new()

        # Load the appropriate JSON file based on user selection
        json_file = json_file_2_panel if st.session_state['selected_aerator'] == "2-Panel" else json_file_4_panel
        with open(json_file, "r") as file:
            pv_inputs = json.load(file)
        # iterate through the input key-value pairs and set the module inputs
        for k, v in pv_inputs.items():
            if k != 'number_inputs':
                # print(f"Setting input: {k} with value: v")
                pv_model.value(k, v)

        pv_model.SystemDesign.subarray1_tilt = st.session_state['tilt'] # Use user-selected tilt

        pv_model.SolarResource.solar_resource_file = nsrdb_fp
        pv_model.execute()
        energy_output = pv_model.Outputs.monthly_dc
        st.session_state['energy_output'] = energy_output  # Store in session state
        status.update(label="Energy Output Calculated!", state="complete")
        st.session_state['processing'] = False

# Display the stored result
if st.session_state['energy_output'] is not None:
    total_energy_output = sum(st.session_state['energy_output'])
    st.header(f" Annual DC Energy Produced")
    st.write(f"Total Annual DC Energy Output: {total_energy_output:.2f} kWh")
    st.header("Monthly Energy Output")
    st.write(
        f"At latitude: {st.session_state['latitude']}, longitude: {st.session_state['longitude']} for a with a **{st.session_state['selected_aerator']}** aerator with a tilt of **{st.session_state['tilt']} degrees**:"
    )

    # Create a DataFrame for the bar chart
    months = [
        'January', 'February', 'March', 'April', 'May', 'June', 
        'July', 'August', 'September', 'October', 'November', 'December']
    energy_data = pd.DataFrame({
        "Month": months,
        "Monthly Energy Production (kWh)": st.session_state['energy_output'],
    })

    # Convert 'Month' column to a categorical type with ordered categories
    energy_data['Month'] = pd.Categorical(energy_data['Month'], categories=months, ordered=True)


    # Display the bar chart
    st.bar_chart(energy_data, x="Month", y="Monthly Energy Production (kWh)")

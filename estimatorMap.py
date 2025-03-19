import numpy as np
import streamlit as st
import folium
from streamlit_folium import st_folium
import glob
import os
import re
import json
import pandas as pd
import PySAM.Pvsamv1 as pv
import PySAM.ResourceTools as tools


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
MAX_FILES = 50  # Maximum number of files to keep

# Initialize session state
if 'energy_output' not in st.session_state:
    st.session_state['energy_output'] = None
if 'processing' not in st.session_state:
    st.session_state['processing'] = False
if 'selected_marker' not in st.session_state:
    st.session_state['selected_marker'] = None
if "map_center" not in st.session_state:
    st.session_state["map_center"] = [38.0367, -84.5078]  # Default: Lexington, KY
if "zoom" not in st.session_state:
    st.session_state["zoom"] = 8
if 'markers' not in st.session_state:
    st.session_state['markers'] = []
if 'selected_marker' not in st.session_state:
    st.session_state['selected_marker'] = None
if 'selected_location' not in st.session_state:
    st.session_state['selected_location'] = None
if 'last_clicked' not in st.session_state:
    st.session_state['last_clicked'] = None
if 'last_object_clicked' not in st.session_state:
    st.session_state['last_object_clicked'] = None
if 'selected_aerator' not in st.session_state:
    st.session_state['selected_aerator'] = "2-Panel"  # Default aerator
if 'tilt' not in st.session_state:
    st.session_state['tilt'] = 15 # Default tilt
if 'calculated_aerator' not in st.session_state:
    st.session_state['calculated_aerator'] = "2-Panel"  # Default aerator
if 'calculated_tilt' not in st.session_state:
    st.session_state['calculated_tilt'] = 15 # Default tilt
if 'calculated_location' not in st.session_state:
    st.session_state['calculated_location'] = None
    

st.header("Select Location")
st.write("Select a location on the map to see the output from the solar aerator.")
st.write("Click anywhere on the map to select a location. The blue marker will move to the selected location.")
st.write("Green markers represent already downloaded data and will process more quickly if selected.")

# Function to extract lat/lon from filename
def extract_lat_lon(filename):
    match = re.search(r"nsrdb_(-?\d+\.\d+)_(-?\d+\.\d+)_", filename)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None

temp_res_dir = 'solar_data/'
# Add markers for existing files
csv_files = glob.glob(os.path.join(temp_res_dir, "*_psm3-tmy_*.csv"))
for csv_file in csv_files:
    lat, lon = extract_lat_lon(os.path.basename(csv_file))
    if lat is not None and lon is not None:
        marker_to_add = folium.Marker(
            location=[lat, lon],
            popup=f"Existing Data: Lat={lat}, Lon={lon}",
            icon=folium.Icon(color='green')  # Use a different color for existing data
        )
        st.session_state["markers"].append(marker_to_add)
 

fg = folium.FeatureGroup(name="Markers")
for marker in st.session_state["markers"]:
    fg.add_child(marker)
if st.session_state['selected_location'] is not None:
    selected_marker_to_add = folium.Marker(
        location=[st.session_state['selected_location']['latitude'], st.session_state['selected_location']['longitude']],
        popup=f"Selected Location: Lat={st.session_state['selected_location']['latitude']}, Lon={st.session_state['selected_location']['longitude']}",
        icon=folium.Icon(color='blue')  # Use a different color for the selected location
    )
    st.session_state["selected_marker"] = selected_marker_to_add
if st.session_state['selected_marker'] is not None:
    fg.add_child(st.session_state['selected_marker'])

# Create a map using folium
m = folium.Map(location=st.session_state['map_center'], zoom_start=5)

# Display the map in Streamlit
map_data = st_folium(m, 
                    center=st.session_state["map_center"],
                    zoom=st.session_state["zoom"],
                    key="new",
                    feature_group_to_add=fg,
                    width=800, 
                    height=600,
                    )
# Get the selected coordinates from the map
if map_data and map_data["last_clicked"]: # Check if map_data and last_clicked exist
    # Check if we have a new location clicked
    if st.session_state['last_clicked'] != map_data["last_clicked"]:
        # Update the last clicked location
        st.session_state['last_clicked'] = map_data["last_clicked"]
        # Update the selected_location to this location
        st.session_state['selected_location'] = {'latitude': None, 'longitude': None} # Erase and Initialize the selected_location dictionary
        st.session_state['selected_location']['latitude'] = round(map_data["last_clicked"]["lat"], 4)
        st.session_state['selected_location']['longitude'] = round(map_data["last_clicked"]["lng"], 4)
        st.rerun()
if map_data and map_data["last_object_clicked"]: # Check if map_data and last_object_clicked exist
    # Check if we have a new object clicked
    if st.session_state['last_object_clicked'] != map_data["last_object_clicked"]:
        # Update the last obejct clicked location
        st.session_state['last_object_clicked'] = map_data["last_object_clicked"]
        # Update the selected_location to this location
        st.session_state['selected_location'] = {'latitude': None, 'longitude': None} # Erase and Initialize the selected_location dictionary
        st.session_state['selected_location']['latitude'] = round(map_data["last_object_clicked"]["lat"], 4)
        st.session_state['selected_location']['longitude'] = round(map_data["last_object_clicked"]["lng"], 4)
        st.rerun()


st.header("Installation Information")
# aerator selection
aerator_type = st.selectbox(
    "Select Aerator Type",
    ["2-Panel", "4-Panel"],
    index=0,  # Default to 2-Panel
    key="aerator_type_selectbox" # Add a key
)
st.session_state['selected_aerator'] = aerator_type # Store selection

# tilt input
tilt = st.number_input("Enter Tilt Angle (degrees)", value=st.session_state['tilt'], min_value=0, max_value=90, key="tilt_input")
st.session_state['tilt'] = tilt # Store tilt
st.header("Calculate Energy Output")
if st.session_state['selected_location'] is not None:
    if st.session_state['selected_location']['latitude'] is not None and st.session_state['selected_location']['longitude']:
        st.write(f"Click the button below to start the calculation for latitude {st.session_state['selected_location']['latitude']} and longitude {st.session_state['selected_location']['longitude']}.")
st.markdown(f"*Note: This may require downloading solar resource data from the National Renewable Energy Laboratory's [National Solar Radiation Database](https://nsrdb.nrel.gov/) and may take a few minutes.*")
st.write("*If it takes too long, the download may have timed out. Try to restart the process by clicking the button again.*")
if st.button("Calculate Energy Output"):  # Wrap the calculation in a button
    if st.session_state['selected_location'] is None:
        st.error("Please select a location on the map first.")
    else:
        st.session_state['processing'] = True
        # Store the selected aerator and tilt that were used in calculating for later display
        st.session_state['calculated_aerator'] = st.session_state['selected_aerator']
        st.session_state['calculated_tilt'] = st.session_state['tilt']
        st.session_state['calculated_location'] = st.session_state['selected_location']


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
        lon_lats = [(st.session_state['selected_location']['longitude'], st.session_state['selected_location']['latitude'])] # Use values from session state
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
        json_file = json_file_2_panel if st.session_state['calculated_aerator'] == "2-Panel" else json_file_4_panel
        with open(json_file, "r") as file:
            pv_inputs = json.load(file)
        # iterate through the input key-value pairs and set the module inputs
        for k, v in pv_inputs.items():
            if k != 'number_inputs':
                pv_model.value(k, v)

        pv_model.SystemDesign.subarray1_tilt = st.session_state['calculated_tilt'] # Use user-selected tilt

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
    st.write(f"At latitude: {st.session_state['selected_location']['latitude']}, longitude: {st.session_state['selected_location']['longitude']} for a with a **{st.session_state['calculated_aerator']}** aerator with a tilt of **{st.session_state['calculated_tilt']} degrees**:"
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

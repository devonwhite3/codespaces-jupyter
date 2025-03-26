import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os
import zipfile

# Define the input CSV and GTFS file paths
CSV_FILE = '/workspaces/codespaces-jupyter/notebooks/Master.csv'  # Replace with the correct path to your CSV file
GTFS_FILE = '/workspaces/codespaces-jupyter/notebooks/google_transit.zip'  # Replace with the correct path to your GTFS file

# Load the CSV into a pandas DataFrame
data = pd.read_csv(CSV_FILE)

# Basic Data Validation
required_columns = {'Route', 'Stop ID', 'Ridership', 'Stop Name', 'Latitude', 'Longitude'}
if not required_columns.issubset(data.columns):
    raise ValueError(f"The CSV file must contain the columns: {', '.join(required_columns)}")

# Ensure Ridership column is numeric
data['Ridership'] = pd.to_numeric(data['Ridership'], errors='coerce').fillna(0)

# Extract GTFS shapes.txt
if not os.path.exists('shapes.txt'):
    with zipfile.ZipFile(GTFS_FILE, 'r') as gtfs_zip:
        gtfs_zip.extract('shapes.txt')

# Load shapes.txt into a DataFrame
shapes = pd.read_csv('shapes.txt')

def create_map(selected_routes=None, output_file="transit_map.html"):
    """Generates the folium map with selected routes and saves it as an HTML file."""
    # Base map
    transit_map = folium.Map(location=[data['Latitude'].mean(), data['Longitude'].mean()], zoom_start=12)

    # Group data by Route
    grouped = data.groupby('Route')

    # Add each route to the map
    for route, stops in grouped:
        if selected_routes and route not in selected_routes:
            continue

        # Choose a color for the route
        color = f"#{hash(route) % 0xFFFFFF:06x}"  # Generate a hex color based on the route
        marker_cluster = MarkerCluster(name=f"Route {route}").add_to(transit_map)

        # Plot stops for the route
        for _, stop in stops.iterrows():
            folium.CircleMarker(
                location=[stop['Latitude'], stop['Longitude']],
                radius=max(3, stop['Ridership'] / 100),  # Scale radius based on ridership
                color=color,
                fill=True,
                fill_opacity=0.6,
                popup=folium.Popup(f"Stop Name: {stop['Stop Name']}<br>"
                                   f"Ridership: {stop['Ridership']}<br>"
                                   f"Route: {route}")
            ).add_to(marker_cluster)

        # Add route shapes from GTFS
        shape_ids = stops['Stop ID'].unique()
        for shape_id in shape_ids:
            shape_data = shapes[shapes['shape_id'] == shape_id]
            if not shape_data.empty:
                shape_coords = shape_data.sort_values('shape_pt_sequence')[['shape_pt_lat', 'shape_pt_lon']].values
                folium.PolyLine(
                    locations=shape_coords,
                    color=color,
                    weight=3,
                    opacity=0.7,
                    tooltip=f"Route Shape for {route}"
                ).add_to(transit_map)

    folium.LayerControl().add_to(transit_map)  # Add layer control to toggle routes

    # Save the map as an HTML file
    transit_map.save(output_file)
    print(f"Map has been saved to {os.path.abspath(output_file)}")

# Create and save the map
create_map()

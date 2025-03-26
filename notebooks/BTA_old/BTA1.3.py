import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os
import zipfile
import openrouteservice
from itertools import permutations

# Define the input CSV and GTFS file paths
CSV_FILE = '/workspaces/codespaces-jupyter/notebooks/Master.csv'  # Replace with the correct path to your CSV file
GTFS_FILE = '/workspaces/codespaces-jupyter/notebooks/google_transit.zip'  # Replace with the correct path to your GTFS file
# Example usage
# API_KEY should be replaced with a valid OpenRouteService API key
API_KEY = '5b3ce3597851110001cf624859558da306674cc2b9890050e4ec89f5'  # Replace with your OpenRouteService API key

# Load the CSV into a pandas DataFrame
data = pd.read_csv(CSV_FILE)

# Basic Data Validation
required_columns = {'Route', 'Stop ID', 'Ridership', 'Stop Name', 'Latitude', 'Longitude'}
if not required_columns.issubset(data.columns):
    raise ValueError(f"The CSV file must contain the columns: {', '.join(required_columns)}")

# Ensure Ridership column is numeric
data['Ridership'] = pd.to_numeric(data['Ridership'], errors='coerce').fillna(0)

# Load GTFS shapes data manually from the zip file
with zipfile.ZipFile(GTFS_FILE, 'r') as gtfs_zip:
    with gtfs_zip.open('shapes.txt') as shapes_file:
        shapes = pd.read_csv(shapes_file)

# Validate column names in shapes.txt
required_shape_columns = {'shape_id', 'shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence'}
if not required_shape_columns.issubset(shapes.columns):
    raise ValueError(f"The shapes.txt file must contain the columns: {', '.join(required_shape_columns)}")

def get_route_path(api_key, coordinates):
    """Fetch the route path connecting stops from OpenRouteService."""
    client = openrouteservice.Client(key=api_key)
    try:
        route = client.directions(
            coordinates=coordinates,
            profile='driving-car',
            format='geojson'
        )
        return [(point[1], point[0]) for point in route['routes'][0]['geometry']['coordinates']]
    except Exception as e:
        print(f"Failed to fetch route path: {e}")
        return None

def create_map(selected_routes=None, api_key=None, output_file="transit_map.html"):
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
        stop_coords = []
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
            stop_coords.append((stop['Longitude'], stop['Latitude']))

        # Connect stops using OpenStreetMap route data
        if api_key and len(stop_coords) > 1:
            route_path = get_route_path(api_key, stop_coords)
            if route_path:
                folium.PolyLine(
                    locations=route_path,
                    color=color,
                    weight=4,
                    opacity=0.8,
                    tooltip=f"Route Path for {route}"
                ).add_to(transit_map)

    # Add layer control for all/no routes
    folium.LayerControl(collapsed=False).add_to(transit_map)

    # Save the map as an HTML file
    transit_map.save(output_file)
    print(f"Map has been saved to {os.path.abspath(output_file)}")


create_map(api_key=API_KEY)

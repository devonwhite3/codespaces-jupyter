import pandas as pd
import geopandas as gpd
import folium
from folium import plugins
import zipfile
import tempfile
import os
from shapely.geometry import LineString, Point
import json
import branca.colormap as cm
import numpy as np


def load_gtfs(gtfs_zip_path):
    """Load GTFS data from zip file into pandas DataFrames."""
    temp_dir = tempfile.mkdtemp()
    
    with zipfile.ZipFile(gtfs_zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    routes = pd.read_csv(os.path.join(temp_dir, 'routes.txt'))
    stops = pd.read_csv(os.path.join(temp_dir, 'stops.txt'))
    trips = pd.read_csv(os.path.join(temp_dir, 'trips.txt'))
    shapes = pd.read_csv(os.path.join(temp_dir, 'shapes.txt'))
    
    return routes, stops, trips, shapes

def create_route_shapes(shapes_df, trips_df, routes_df):
    """Create GeoJSON features for each route's shape."""
    route_shapes = {}
    
    for route_id in routes_df['route_id'].unique():
        # Get shape_ids for this route
        route_trips = trips_df[trips_df['route_id'] == route_id]
        shape_ids = route_trips['shape_id'].unique()
        
        for shape_id in shape_ids:
            shape_points = shapes_df[shapes_df['shape_id'] == shape_id].sort_values('shape_pt_sequence')
            
            if not shape_points.empty:
                coords = [[point.shape_pt_lat, point.shape_pt_lon] 
                         for _, point in shape_points.iterrows()]
                
                route_shapes[route_id] = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': [[lon, lat] for lat, lon in coords]
                    },
                    'properties': {
                        'route_id': route_id,
                        'route_name': routes_df[routes_df['route_id'] == route_id]['route_long_name'].iloc[0]
                    }
                }
    
    return route_shapes

def create_map(gtfs_zip_path, ridership_csv_path, output_html_path):
    """Create interactive map with GTFS routes and ridership data."""
    # Load GTFS data
    routes_df, stops_df, trips_df, shapes_df = load_gtfs(gtfs_zip_path)
    
    # Load ridership data
    ridership_df = pd.read_csv(ridership_csv_path)
    
    # Create base map centered on the mean of all stops
    center_lat = stops_df['stop_lat'].mean()
    center_lon = stops_df['stop_lon'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
    
    # Create route shapes
    route_shapes = create_route_shapes(shapes_df, trips_df, routes_df)
    
    # Generate color map for routes
    colors = cm.LinearColormap(
        colors=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', 
                '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'],
        index=np.linspace(0, 1, 10)
    ).to_step(10)
    
    # Create layer control
    route_layers = {}
    
    # Add route shapes to map
    for i, (route_id, shape) in enumerate(route_shapes.items()):
        route_color = colors.rgb_hex_str(i / len(route_shapes))
        
        # Create GeoJSON layer for route
        route_layer = folium.GeoJson(
            shape,
            name=f"Route {route_id}",
            style_function=lambda x, color=route_color: {
                'color': color,
                'weight': 3,
                'opacity': 0.7
            }
        )
        
        route_layers[route_id] = route_layer
        route_layer.add_to(m)
    
    # Create stop markers with ridership information
    stop_groups = {}
    
    for route_id in route_shapes.keys():
        stop_groups[route_id] = folium.FeatureGroup(name=f"Stops Route {route_id}", show=False)
    
    for _, stop_data in ridership_df.iterrows():
        route_id = stop_data['Route']
        ridership = stop_data['Ridership']
        radius = np.sqrt(ridership) * 2  # Scale marker size based on ridership
        
        popup_text = f"""
        <b>Stop:</b> {stop_data['Stop Name']}<br>
        <b>Stop ID:</b> {stop_data['Stop ID']}<br>
        <b>Ridership:</b> {ridership}<br>
        <b>Route:</b> {route_id}
        """
        
        if route_id in stop_groups:
            marker = folium.CircleMarker(
                location=[stop_data['Latitude'], stop_data['Longitude']],
                radius=radius,
                popup=folium.Popup(popup_text, max_width=300),
                color=colors.rgb_hex_str(list(route_shapes.keys()).index(route_id) / len(route_shapes)),
                fill=True,
                fill_opacity=0.7
            )
            marker.add_to(stop_groups[route_id])
    
    # Add stop groups to map
    for group in stop_groups.values():
        group.add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    m.save(output_html_path)

# Example usage
if __name__ == "__main__":
    create_map(
        gtfs_zip_path="/workspaces/codespaces-jupyter/notebooks/google_transit.zip",
        ridership_csv_path="/workspaces/codespaces-jupyter/notebooks/Master.csv",
        output_html_path="transit_map.html"
    )
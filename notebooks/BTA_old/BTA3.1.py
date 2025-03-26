import pandas as pd
import folium
from folium import FeatureGroup, CircleMarker
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import zipfile
from io import BytesIO
import base64
from math import cos, sin, radians
import math

# Load GTFS feed data
def load_gtfs_data(gtfs_zip_path):
    # Read GTFS data
    with zipfile.ZipFile(gtfs_zip_path, 'r') as gtfs_zip:
        routes = pd.read_csv(BytesIO(gtfs_zip.read("routes.txt")))
        shapes = pd.read_csv(BytesIO(gtfs_zip.read("shapes.txt")))
        trips = pd.read_csv(BytesIO(gtfs_zip.read("trips.txt")))
        stops = pd.read_csv(BytesIO(gtfs_zip.read("stops.txt")))
        stop_times = pd.read_csv(BytesIO(gtfs_zip.read("stop_times.txt")))

    print("GTFS Data - Routes, Trips, and Stop Times:")
    print("Routes:", routes.head())
    print("Trips:", trips.head())
    print("Stop Times:", stop_times.head())

    return routes, shapes, trips, stops, stop_times

def load_ridership_data(ridership_path):
    """Load ridership data from CSV file."""
    ridership_df = pd.read_csv(ridership_path)
    ridership_df['Stop'] = ridership_df['Stop'].astype(str)  # Ensure Stop column is string
    ridership_df['Route'] = ridership_df['Route'].astype(str)  # Ensure Route column is string
    ridership_df['Ridership'] = ridership_df['Ridership'].str.replace(',', '').astype(int)
    print("Initial Ridership Data:")
    print(ridership_df.head())
    print("Total Rows in Ridership File:", len(ridership_df))
    return ridership_df

# Process data
def process_routes(routes, shapes, trips, stop_times):
    # Normalize IDs to strings
    routes['route_id'] = routes['route_id'].astype(str)
    trips['route_id'] = trips['route_id'].astype(str)
    stop_times['stop_id'] = stop_times['stop_id'].astype(str)

    # Map route_id to shapes
    route_shapes = trips[['route_id', 'shape_id']].drop_duplicates()
    routes = routes.merge(route_shapes, on='route_id')

    # Associate stops with routes
    stop_routes = trips[['route_id', 'trip_id']].merge(stop_times[['trip_id', 'stop_id']], on='trip_id')
    stop_routes = stop_routes.drop_duplicates()
    print("Stop Routes (Deduplicated):")
    print(stop_routes.head())
    print("Total Stop Routes (Deduplicated):", len(stop_routes))

    return routes, shapes, stops, stop_routes

def create_pie_chart_marker(colors, stop_name):
    total_slices = len(colors)
    pie_chart_svg = '<svg width="40" height="40" viewBox="0 0 2 2" xmlns="http://www.w3.org/2000/svg">'
    angle_step = 360 / total_slices
    for i, color in enumerate(colors):
        start_angle = angle_step * i
        end_angle = angle_step * (i + 1)
        large_arc_flag = 1 if end_angle - start_angle > 180 else 0
        path_d = f"M 1 1 L {1 + 1 * cos(radians(start_angle))} {1 + 1 * sin(radians(start_angle))} A 1 1 0 {large_arc_flag} 1 {1 + 1 * cos(radians(end_angle))} {1 + 1 * sin(radians(end_angle))} Z"
        pie_chart_svg += f'<path d="{path_d}" fill="{color}" stroke="black" stroke-width="0.05"/>'
    pie_chart_svg += '</svg>'
    encoded_svg = base64.b64encode(pie_chart_svg.encode('utf-8')).decode('utf-8')
    return f'<img src="data:image/svg+xml;base64,{encoded_svg}" alt="{stop_name}" width="40" height="40">'

def create_map(routes, shapes, stops, stop_routes, ridership_df, active_routes=None):
    if active_routes is None:
        active_routes = ["1"]  # Default to showing Route 1

    # Normalize stop_id as string for all DataFrames
    stops['stop_id'] = stops['stop_id'].astype(str)
    stop_routes['stop_id'] = stop_routes['stop_id'].astype(str)
    ridership_df['Stop'] = ridership_df['Stop'].astype(str)

    # Filter stops for active routes only
    active_stop_ids = stop_routes[stop_routes['route_id'].isin(active_routes)]['stop_id'].unique()
    active_stops = stops[stops['stop_id'].isin(active_stop_ids)].copy()

    # Debugging output
    print("Active Routes:", active_routes)
    print("Unique Stop IDs for Active Routes:", active_stop_ids)
    print("Active Stops after Filtering:")
    print(active_stops.head())

    # Aggregate ridership for each stop across active routes
    stop_ridership = ridership_df[ridership_df['Route'].isin(active_routes)].groupby(['Stop'])['Ridership'].sum().reset_index()

    # Debugging aggregated ridership
    print("Aggregated Ridership for Active Routes:")
    print(stop_ridership.head())

    # Merge active stops with ridership data
    active_stops = active_stops.merge(
        stop_ridership, 
        left_on='stop_id', 
        right_on='Stop', 
        how='left'
    )
    active_stops['Ridership'] = active_stops['Ridership'].fillna(0)

    # Debugging post-merge active stops
    print("Active Stops after Merging with Ridership:")
    print(active_stops[['stop_id', 'stop_lat', 'stop_lon', 'stop_name', 'Ridership']].head())

    # Assign colors based on GTFS feed
    route_colors = routes.set_index('route_id')['route_color'].to_dict()

    transit_map = folium.Map(location=[37.7749, -122.4194], zoom_start=13)
    bounds = []

    # Add stops to the map
    for _, stop in active_stops.iterrows():
        # Get the route colors for the stop that are currently active
        stop_route_ids = stop_routes[
            (stop_routes['stop_id'] == stop['stop_id']) & 
            (stop_routes['route_id'].isin(active_routes))
        ]['route_id'].unique()
        
        stop_colors = ["#" + route_colors.get(route_id, "000000") for route_id in stop_route_ids]

        # Calculate marker size based on ridership (scale ridership logarithmically)
        stop_ridership = stop['Ridership']
        marker_size = max(8, min(25, 8 + int(math.log(stop_ridership + 1) * 3)))

        # Create transfer station only if multiple active routes use the stop
        if len(stop_colors) > 1:
            # Create pie chart marker for transfer points
            icon_html = create_pie_chart_marker(stop_colors, stop['stop_name'])
            marker = folium.Marker(
                location=[stop['stop_lat'], stop['stop_lon']],
                icon=folium.DivIcon(
                    html=icon_html, 
                    icon_size=(marker_size*2, marker_size*2),
                    icon_anchor=(marker_size, marker_size)
                ),
                tooltip=f"Transfer Station: {stop['stop_name']} (Ridership: {stop_ridership})"
            )
        else:
            color = stop_colors[0]
            marker = CircleMarker(
                location=[stop['stop_lat'], stop['stop_lon']],
                radius=marker_size,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                tooltip=f"{stop['stop_name']} (Ridership: {stop_ridership})"
            )

        marker.add_to(transit_map)

    # Add routes to the map (existing code remains the same)
    for route_id in active_routes:
        color = "#" + route_colors.get(route_id, "000000")
        group = FeatureGroup(name=f"Route {route_id}", control=True)

        for shape_id in routes[routes['route_id'] == route_id]['shape_id']:
            shape_points = shapes[shapes['shape_id'] == shape_id][['shape_pt_lat', 'shape_pt_lon']].values.tolist()
            polyline = folium.PolyLine(locations=shape_points, color=color, weight=3, opacity=0.8)
            polyline.add_to(group)
            bounds.extend(shape_points)

        group.add_to(transit_map)

    folium.LayerControl().add_to(transit_map)
    if bounds:
        transit_map.fit_bounds(bounds)

    return transit_map

# Generate the app
def generate_app(routes, shapes, stops, stop_routes, ridership_df, map_file):
    app = dash.Dash(__name__)
    route_options = [{"label": f"Route {route_id}", "value": route_id} for route_id in routes['route_id'].unique()]

    app.layout = html.Div([
        html.H1("GTFS Route Viewer with Ridership"),
        dcc.Checklist(
            id="route-selector",
            options=route_options,
            value=["1"],
            inline=True
        ),
        html.Iframe(id="map", srcDoc=open(map_file, "r").read(), width="100%", height="600")
    ])

    @app.callback(
        Output("map", "srcDoc"),
        Input("route-selector", "value")
    )
    def update_map(selected_routes):
        updated_map = create_map(routes, shapes, stops, stop_routes, ridership_df, active_routes=selected_routes)
        updated_map.save(map_file)
        return open(map_file, "r").read()

    return app

# Main
if __name__ == "__main__":
    gtfs_zip_path = "notebooks/google_transit.zip"  # Update this path as needed
    ridership_path = "notebooks/ridership.csv"  # Path to ridership CSV

    # Load and process GTFS data
    routes, shapes, trips, stops, stop_times = load_gtfs_data(gtfs_zip_path)
    routes, shapes, stops, stop_routes = process_routes(routes, shapes, trips, stop_times)

    # Load ridership data
    ridership_df = load_ridership_data(ridership_path)

    # Create the initial map with Route 1 visible
    map_file = "transit_map.html"
    base_map = create_map(routes, shapes, stops, stop_routes, ridership_df, active_routes=["1"])
    base_map.save(map_file)

    # Run the Dash app
    app = generate_app(routes, shapes, stops, stop_routes, ridership_df, map_file)
    app.run_server(debug=True)

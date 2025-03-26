import pandas as pd
import folium
from folium import FeatureGroup
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import zipfile
from io import BytesIO
import os

# Load GTFS feed data from a single zip file
def load_single_gtfs_data(gtfs_zip_path):
    with zipfile.ZipFile(gtfs_zip_path, 'r') as gtfs_zip:
        routes = pd.read_csv(BytesIO(gtfs_zip.read("routes.txt")), dtype={"route_id": str})
        shapes = pd.read_csv(BytesIO(gtfs_zip.read("shapes.txt")), dtype={"shape_id": str, "shape_pt_lat": float, "shape_pt_lon": float})
        trips = pd.read_csv(BytesIO(gtfs_zip.read("trips.txt")), dtype={"route_id": str, "trip_id": str, "shape_id": str})
        stops = pd.read_csv(BytesIO(gtfs_zip.read("stops.txt")), dtype={"stop_id": str, "stop_lat": float, "stop_lon": float})
        stop_times = pd.read_csv(BytesIO(gtfs_zip.read("stop_times.txt")), dtype={"trip_id": str, "stop_id": str})

    return routes, shapes, trips, stops, stop_times

# Load GTFS data from all zip files in a folder
def load_gtfs_from_folder(folder_path):
    all_routes, all_shapes, all_trips, all_stops, all_stop_times = [], [], [], [], []

    for file_name in os.listdir(folder_path):
        if file_name.endswith('.zip'):
            gtfs_zip_path = os.path.join(folder_path, file_name)
            routes, shapes, trips, stops, stop_times = load_single_gtfs_data(gtfs_zip_path)

            all_routes.append(routes)
            all_shapes.append(shapes)
            all_trips.append(trips)
            all_stops.append(stops)
            all_stop_times.append(stop_times)

    # Concatenate all dataframes
    routes = pd.concat(all_routes, ignore_index=True).drop_duplicates()
    shapes = pd.concat(all_shapes, ignore_index=True).drop_duplicates()
    trips = pd.concat(all_trips, ignore_index=True).drop_duplicates()
    stops = pd.concat(all_stops, ignore_index=True).drop_duplicates()
    stop_times = pd.concat(all_stop_times, ignore_index=True).drop_duplicates()

    return routes, shapes, trips, stops, stop_times

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

    return routes, shapes, stops, stop_routes

def create_map(routes, shapes, stops, stop_routes, active_routes=None):
    if active_routes is None:
        active_routes = ["1"]  # Default to showing Route 1

    # Normalize stop_id as string for all DataFrames
    stops['stop_id'] = stops['stop_id'].astype(str)
    stop_routes['stop_id'] = stop_routes['stop_id'].astype(str)

    # Filter stops for active routes only
    active_stop_ids = stop_routes[stop_routes['route_id'].isin(active_routes)]['stop_id'].unique()
    active_stops = stops[stops['stop_id'].isin(active_stop_ids)].copy()

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
        
        stop_colors = ["#" + str(route_colors.get(route_id, "000000")) for route_id in stop_route_ids]

        # Create the tooltip details
        tooltip_text = f"{stop['stop_name']}"

        color = stop_colors[0] if stop_colors else "#000000"
        marker = folium.CircleMarker(
            location=[stop['stop_lat'], stop['stop_lon']],
            radius=8,  # Fixed marker size
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            tooltip=tooltip_text
        )

        marker.add_to(transit_map)

    # Add routes to the map (existing code remains the same)
    for route_id in active_routes:
        color = "#" + str(route_colors.get(route_id, "000000"))
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
def generate_app(routes, shapes, stops, stop_routes, map_file):
    app = dash.Dash(__name__)
    route_options = [{"label": f"Route {route_id}", "value": route_id} for route_id in routes['route_id'].unique()]

    app.layout = html.Div([
        html.H1("GTFS Route Viewer"),
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
        updated_map = create_map(routes, shapes, stops, stop_routes, active_routes=selected_routes)
        updated_map.save(map_file)
        return open(map_file, "r").read()

    return app

# Main
if __name__ == "__main__":
    gtfs_folder_path = "notebooks/Regional GTFS"  # Update this path to your GTFS folder

    # Load and process GTFS data
    routes, shapes, trips, stops, stop_times = load_gtfs_from_folder(gtfs_folder_path)
    routes, shapes, stops, stop_routes = process_routes(routes, shapes, trips, stop_times)

    # Create the initial map with Route 1 visible
    map_file = "transit_map.html"
    base_map = create_map(routes, shapes, stops, stop_routes, active_routes=["1"])
    base_map.save(map_file)

    # Run the Dash app
    app = generate_app(routes, shapes, stops, stop_routes, map_file)
    app.run_server(debug=True)

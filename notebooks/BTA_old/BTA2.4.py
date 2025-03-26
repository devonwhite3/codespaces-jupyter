import pandas as pd
import folium
from folium import FeatureGroup
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import zipfile
from io import BytesIO

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

# Create the folium map
def create_map(routes, shapes, stops, stop_routes, active_routes=None):
    if active_routes is None:
        active_routes = ["1"]  # Default to showing Route 1

    # Normalize stop_id as string for all DataFrames
    stops['stop_id'] = stops['stop_id'].astype(str)
    stop_routes['stop_id'] = stop_routes['stop_id'].astype(str)

    # Filter stops for active routes only
    active_stop_ids = stop_routes[stop_routes['route_id'].isin(active_routes)]['stop_id'].unique()
    active_stops = stops[stops['stop_id'].isin(active_stop_ids)]

    # Assign colors based on GTFS feed
    route_colors = routes.set_index('route_id')['route_color'].to_dict()

    transit_map = folium.Map(location=[37.7749, -122.4194], zoom_start=13)
    bounds = []

    # Add stops to the map
    for _, stop in active_stops.iterrows():
        # Get the route color for the stop
        route_id = stop_routes[stop_routes['stop_id'] == stop['stop_id']]['route_id'].values[0]
        color = "#" + route_colors.get(route_id, "000000")  # Fallback to black if no color provided

        folium.CircleMarker(
            location=[stop['stop_lat'], stop['stop_lon']],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            tooltip=stop['stop_name']
        ).add_to(transit_map)

    # Add routes to the map
    for route_id in active_routes:
        color = "#" + route_colors.get(route_id, "000000")  # Fallback to black if no color provided
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
    gtfs_zip_path = "notebooks/google_transit.zip"  # Update this path as needed

    # Load and process GTFS data
    routes, shapes, trips, stops, stop_times = load_gtfs_data(gtfs_zip_path)
    routes, shapes, stops, stop_routes = process_routes(routes, shapes, trips, stop_times)

    # Create the initial map with Route 1 visible
    map_file = "transit_map.html"
    base_map = create_map(routes, shapes, stops, stop_routes, active_routes=["1"])
    base_map.save(map_file)

    # Run the Dash app
    app = generate_app(routes, shapes, stops, stop_routes, map_file)
    app.run_server(debug=True)

import pandas as pd
import folium
from folium import FeatureGroup, Marker
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import zipfile
from io import BytesIO

# Load GTFS feed from a ZIP file
def load_gtfs_from_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as gtfs_zip:
        routes = pd.read_csv(BytesIO(gtfs_zip.read("routes.txt")))
        shapes = pd.read_csv(BytesIO(gtfs_zip.read("shapes.txt")))
        trips = pd.read_csv(BytesIO(gtfs_zip.read("trips.txt")))
        stops = pd.read_csv(BytesIO(gtfs_zip.read("stops.txt")))
        stop_times = pd.read_csv(BytesIO(gtfs_zip.read("stop_times.txt")))
    return routes, shapes, trips, stops, stop_times

# Process data
def process_data(routes, shapes, trips, stop_times, ridership):
    # Merge trips with shapes and routes to associate each route with shapes
    route_shapes = trips[['route_id', 'shape_id']].drop_duplicates()
    routes = routes.merge(route_shapes, on='route_id')

    # Normalize `stop_id` to ensure consistent formatting
    trips['route_id'] = trips['route_id'].astype(str)
    stop_times['stop_id'] = stop_times['stop_id'].astype(str)
    ridership['route_id'] = ridership['route_id'].astype(str)
    ridership['stop_id'] = ridership['stop_id'].astype(str)

    # Merge ridership data with stop routes
    stop_routes = trips[['route_id', 'trip_id']].merge(stop_times[['trip_id', 'stop_id']], on='trip_id')
    stop_routes_ridership = stop_routes.merge(ridership, on=['route_id', 'stop_id'], how='left')

    # Replace any missing ridership values with 0
    stop_routes_ridership['Ridership'] = pd.to_numeric(stop_routes_ridership['Ridership'], errors='coerce').fillna(0)

    return routes, shapes, stops, stop_routes_ridership

# Create the folium map
def create_map(routes, shapes, stops, stop_routes, active_routes=None):
    if active_routes is None:
        active_routes = ["1"]  # Default to showing Route 1

    route_colors = {
        route_id: f"#{hash(route_id) % 0xFFFFFF:06x}" for route_id in routes['route_id'].unique()
    }

    transit_map = folium.Map(location=[37.7749, -122.4194], zoom_start=13)
    bounds = []

    for route_id in active_routes:
        color = route_colors.get(route_id, "blue")
        group = FeatureGroup(name=f"Route {route_id}", control=True)

        # Add shapes to map
        for shape_id in routes[routes['route_id'] == route_id]['shape_id']:
            shape_points = shapes[shapes['shape_id'] == shape_id][['shape_pt_lat', 'shape_pt_lon']].values.tolist()  # Convert to list
            polyline = folium.PolyLine(
                locations=shape_points, color=color, weight=3, opacity=0.8
            )
            polyline.add_to(group)
            bounds.extend(shape_points)

        # Add stops to map
        route_stops = stops[stops['stop_id'].isin(stop_routes[stop_routes['route_id'] == route_id]['stop_id'])]
        for _, stop in route_stops.iterrows():
            Marker([stop['stop_lat'], stop['stop_lon']], tooltip=stop['stop_name']).add_to(group)

        group.add_to(transit_map)

    folium.LayerControl().add_to(transit_map)

    # Adjust map bounds to fit all active routes
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
            value=["1"],  # Default to Route 1 being selected
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
    zip_path = "/workspaces/codespaces-jupyter/notebooks/google_transit.zip"  # Path to GTFS ZIP file
    ridership_file = "notebooks/Master.csv"


    # Load and process GTFS + Ridership data
    routes, shapes, trips, stops, stop_times, ridership = load_gtfs_and_ridership(gtfs_zip_path, ridership_file)
    routes, shapes, stops, stop_routes_ridership = process_data(routes, shapes, trips, stop_times, ridership)

    # Create the initial map with Route 1 visible
    map_file = "transit_map.html"
    base_map = create_map(routes, shapes, stops, stop_routes, active_routes=["1"])
    base_map.save(map_file)

    # Run the Dash app
    app = generate_app(routes, shapes, stops, stop_routes, map_file)
    app.run_server(debug=True)

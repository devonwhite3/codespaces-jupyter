import pandas as pd
import folium
from folium import FeatureGroup, CircleMarker
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import zipfile
from io import BytesIO

# Load GTFS feed and ridership data
def load_gtfs_and_ridership(gtfs_zip_path, ridership_file):
    # Read GTFS data
    with zipfile.ZipFile(gtfs_zip_path, 'r') as gtfs_zip:
        routes = pd.read_csv(BytesIO(gtfs_zip.read("routes.txt")))
        shapes = pd.read_csv(BytesIO(gtfs_zip.read("shapes.txt")))
        trips = pd.read_csv(BytesIO(gtfs_zip.read("trips.txt")))
        stops = pd.read_csv(BytesIO(gtfs_zip.read("stops.txt")))
        stop_times = pd.read_csv(BytesIO(gtfs_zip.read("stop_times.txt")))

    # Load ridership data
    ridership = pd.read_csv(ridership_file)
    ridership = ridership.rename(columns={"Route": "route_id", "Stop ID": "stop_id", "Ridership": "ridership"})
    ridership['ridership'] = pd.to_numeric(ridership['ridership'], errors='coerce').fillna(0)
    ridership['stop_id'] = ridership['stop_id'].astype(str).str.strip()
    ridership['route_id'] = ridership['route_id'].astype(str).str.strip()

    return routes, shapes, trips, stops, stop_times, ridership

# Process data
def process_routes(routes, shapes, trips, stop_times, ridership):
    # Normalize IDs to strings
    routes['route_id'] = routes['route_id'].astype(str)
    trips['route_id'] = trips['route_id'].astype(str)
    stop_times['stop_id'] = stop_times['stop_id'].astype(str)
    ridership['route_id'] = ridership['route_id'].astype(str)
    ridership['stop_id'] = ridership['stop_id'].astype(str)

    # Debug: Ridership Summary in CSV
    print("\nRidership Summary by Route in CSV:")
    print(ridership.groupby('route_id')['ridership'].sum())

    # Map route_id to shapes
    route_shapes = trips[['route_id', 'shape_id']].drop_duplicates()
    routes = routes.merge(route_shapes, on='route_id')

    # Associate stops with routes
    stop_routes = trips[['route_id', 'trip_id']].merge(stop_times[['trip_id', 'stop_id']], on='trip_id')

    # Stops in GTFS stop_times not found in ridership.csv
    missing_stops_in_ridership = set(stop_times['stop_id']) - set(ridership['stop_id'])
    print("\nStops in GTFS but not in ridership.csv:")
    print(missing_stops_in_ridership)

    # Stops in ridership.csv not found in GTFS stop_times
    missing_stops_in_gtfs = set(ridership['stop_id']) - set(stop_times['stop_id'])
    print("\nStops in ridership.csv but not in GTFS stop_times:")
    print(missing_stops_in_gtfs)


    # Routes in ridership.csv missing in GTFS
    missing_routes_in_gtfs = set(ridership['route_id']) - set(trips['route_id'])
    print("\nRoutes in ridership.csv but not in GTFS trips:")
    print(missing_routes_in_gtfs)

    # Routes in GTFS missing in ridership.csv
    missing_routes_in_ridership = set(trips['route_id']) - set(ridership['route_id'])
    print("\nRoutes in GTFS trips but not in ridership.csv:")
    print(missing_routes_in_ridership)


    # Merge ridership data
    stop_routes_ridership = stop_routes.merge(
        ridership,
        on=['route_id', 'stop_id'],
        how='left'
    ).fillna({'ridership': 0})

    # Debug: Final merged data
    print("\nFinal Merged Data (By Route and Stop):")
    print(stop_routes_ridership.groupby(['route_id', 'stop_id'])['ridership'].sum())

    # Debug: Summarize ridership across routes
    print("\nTotal Ridership Summary by Route (Merged Data):")
    print(stop_routes_ridership.groupby('route_id')['ridership'].sum())

    

    return routes, shapes, stops, stop_routes_ridership


# Create the folium map
def create_map(routes, shapes, stops, stop_routes_ridership, active_routes=None):
    if active_routes is None:
        active_routes = ["1"]  # Default to showing Route 1

    # Normalize stop_id as string for all DataFrames
    stops['stop_id'] = stops['stop_id'].astype(str)
    stop_routes_ridership['stop_id'] = stop_routes_ridership['stop_id'].astype(str)

    # Generate a unique color palette for routes
    unique_routes = sorted(routes['route_id'].unique())
    route_colors = {route_id: f"#{hash(route_id) % 0xFFFFFF:06x}" for route_id in unique_routes}

    transit_map = folium.Map(location=[37.7749, -122.4194], zoom_start=13)
    bounds = []

    for route_id in active_routes:
        color = route_colors.get(route_id, "blue")
        group = FeatureGroup(name=f"Route {route_id}", control=True)

        # Add route shapes
        for shape_id in routes[routes['route_id'] == route_id]['shape_id']:
            shape_points = shapes[shapes['shape_id'] == shape_id][['shape_pt_lat', 'shape_pt_lon']].values.tolist()
            polyline = folium.PolyLine(locations=shape_points, color=color, weight=3, opacity=0.8)
            polyline.add_to(group)
            bounds.extend(shape_points)

        # Add stops with ridership
        try:
            route_stops = stops.merge(
                stop_routes_ridership[stop_routes_ridership['route_id'] == route_id], 
                on='stop_id'
            )
        except ValueError as e:
            print(f"Merge Error: {e}")
            print(f"Stops DataFrame types:\n{stops.dtypes}")
            print(f"Stop Routes Ridership DataFrame types:\n{stop_routes_ridership.dtypes}")
            raise e

        for _, stop in route_stops.iterrows():
            routes_at_stop = ", ".join(sorted(map(str, set(
                stop_routes_ridership[stop_routes_ridership['stop_id'] == stop['stop_id']]['route_id']
            ))))
            circle_size = max(5, (stop['ridership'] ** 0.5) / 2)

            CircleMarker(
                location=[stop['stop_lat'], stop['stop_lon']],
                radius=circle_size,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                tooltip=f"<b>Stop Name:</b> {stop['stop_name']}<br><b>Routes:</b> {routes_at_stop}<br><b>Ridership:</b> {int(stop['ridership'])}"
            ).add_to(group)

        group.add_to(transit_map)

    folium.LayerControl().add_to(transit_map)
    if bounds:
        transit_map.fit_bounds(bounds)

    return transit_map

# Generate the app
def generate_app(routes, shapes, stops, stop_routes_ridership, map_file):
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
        updated_map = create_map(routes, shapes, stops, stop_routes_ridership, active_routes=selected_routes)
        updated_map.save(map_file)
        return open(map_file, "r").read()

    return app

# Main
if __name__ == "__main__":
    gtfs_zip_path = "notebooks/google_transit.zip"  # Update this path as needed
    ridership_file = "notebooks/ridership.csv"  # Use the cleaned ridership file

    # Load and process GTFS data
    routes, shapes, trips, stops, stop_times, ridership = load_gtfs_and_ridership(gtfs_zip_path, ridership_file)
    routes, shapes, stops, stop_routes_ridership = process_routes(routes, shapes, trips, stop_times, ridership)

    # Create the initial map with Route 1 visible
    map_file = "transit_map.html"
    base_map = create_map(routes, shapes, stops, stop_routes_ridership, active_routes=["1"])
    base_map.save(map_file)

    # Run the Dash app
    app = generate_app(routes, shapes, stops, stop_routes_ridership, map_file)
    app.run_server(debug=True)

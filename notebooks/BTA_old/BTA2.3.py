import pandas as pd
import folium
from folium import FeatureGroup
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

    # Map route_id to shapes
    route_shapes = trips[['route_id', 'shape_id']].drop_duplicates()
    routes = routes.merge(route_shapes, on='route_id')

    # Associate stops with routes
    stop_routes = trips[['route_id', 'trip_id']].merge(stop_times[['trip_id', 'stop_id']], on='trip_id')

    # Merge ridership data
    stop_routes_ridership = stop_routes.merge(
        ridership,
        on=['route_id', 'stop_id'],
        how='left'
    ).fillna({'ridership': 0})

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

    # Group data to find transfer points
    grouped_stops = stop_routes_ridership[stop_routes_ridership['route_id'].isin(active_routes)]
    grouped_stops = grouped_stops.groupby('stop_id').agg({
        'ridership': 'sum',
        'route_id': lambda x: list(x.unique()),
    }).reset_index()

    # Add stops and transfer points to the map
    for _, stop in stops.iterrows():
        if stop['stop_id'] in grouped_stops['stop_id'].values:
            stop_info = grouped_stops[grouped_stops['stop_id'] == stop['stop_id']].iloc[0]
            stop_routes = stop_info['route_id']

            if len(stop_routes) > 1:  # Transfer point
                pie_html = """<div style='position:relative; width:20px; height:20px; border-radius:50%; background: conic-gradient("""
                total = len(stop_routes)
                for i, route in enumerate(stop_routes):
                    color = route_colors.get(route, "black")
                    start = (i / total) * 360
                    end = ((i + 1) / total) * 360
                    pie_html += f"{color} {start}deg {end}deg,"  # Define the pie segment
                pie_html = pie_html.rstrip(',') + ");'></div>"

                folium.Marker(
                    location=[stop['stop_lat'], stop['stop_lon']],
                    icon=folium.DivIcon(html=f"""
                        <div style='position: relative; width: 24px; height: 24px; border-radius: 50%;'>
                            {pie_html}
                        </div>
                    """),
                    tooltip=f"Transfer point: {len(stop_routes)} routes ({', '.join(stop_routes)})"
                ).add_to(transit_map)
            else:
                route_color = route_colors.get(stop_routes[0], "blue")
                folium.CircleMarker(
                    location=[stop['stop_lat'], stop['stop_lon']],
                    radius=5,
                    color=route_color,
                    fill=True,
                    fill_color=route_color,
                    fill_opacity=0.7
                ).add_to(transit_map)

    for route_id in active_routes:
        color = route_colors.get(route_id, "blue")
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
    ridership_file = "notebooks/ridership.csv"  # Use the updated ridership file

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

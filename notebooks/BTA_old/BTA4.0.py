import os
import folium
import gtfs_kit as gk
import pandas as pd
import argparse
from shapely.geometry import LineString
from folium.plugins import FeatureGroupSubGroup

# Default center: Pittsburgh, PA
DEFAULT_CENTER = [40.4406, -79.9959]

class TransitMapApp:
    def __init__(self):
        self.gtfs_feeds = {}  # Stores all loaded GTFS feeds
        self.map = folium.Map(location=DEFAULT_CENTER, zoom_start=12)

    def load_gtfs(self, folder_path):
        """Loads all GTFS feeds from the specified folder."""
        for filename in os.listdir(folder_path):
            if filename.endswith('.zip'):
                feed_path = os.path.join(folder_path, filename)
                try:
                    feed = gk.read_feed(feed_path, dist_units='km')
                    self.gtfs_feeds[filename] = feed
                    print(f"✅ Loaded GTFS feed: {filename}")
                except Exception as e:
                    print(f"❌ Error loading {filename}: {e}")

    def display_routes(self):
        """Displays all routes, grouped by GTFS feed, with dropdown selections."""
        for feed_name, feed in self.gtfs_feeds.items():
            feed_group = folium.FeatureGroup(name=f"🚆 {feed_name}", show=False).add_to(self.map)

            routes = feed.routes
            shapes = feed.shapes
            trips = feed.trips
            stops = feed.stops
            stop_times = feed.stop_times

            for _, route in routes.iterrows():
                route_id = route.route_id
                route_name = route.route_long_name
                route_color = f"#{route.route_color}" if pd.notna(route.route_color) else "blue"

                # Group for this route under its feed
                route_group = FeatureGroupSubGroup(feed_group, name=f"{route_name} ({route_id})")

                # ---- GTFS Shape Line (Accurate road-following line) ----
                trip_sample = trips[trips.route_id == route_id]
                if not trip_sample.empty:
                    shape_id = trip_sample.shape_id.iloc[0]

                    if shape_id in shapes.shape_id.values:
                        shape_points = shapes[shapes.shape_id == shape_id].sort_values("shape_pt_sequence")

                        if not shape_points.empty:
                            lat_lon_pairs = list(zip(shape_points.shape_pt_lat.tolist(), shape_points.shape_pt_lon.tolist()))

                            folium.PolyLine(
                                locations=lat_lon_pairs,
                                color=route_color,
                                weight=4,
                                opacity=0.8,
                                popup=f"Route: {route_name} ({route_id})"
                            ).add_to(route_group)
                        else:
                            print(f"⚠️ Warning: No shape points found for route {route_id}")

                # ---- Display Stops ----
                self.display_stops(feed, route_id, route_color, route_group)
                route_group.add_to(self.map)

        folium.LayerControl(collapsed=False).add_to(self.map)
        self.map.save("transit_map.html")
        print("🗺️ Map updated: transit_map.html (open in browser)")

    def display_stops(self, feed, route_id, route_color, route_group):
        """Displays stops for the selected route with route-colored circles."""
        stops = feed.stops
        stop_times = feed.stop_times
        trips = feed.trips

        # Filter stops for the selected route
        trip_ids = trips[trips.route_id == route_id].trip_id
        stop_times_filtered = stop_times[stop_times.trip_id.isin(trip_ids)]
        stops_filtered = stops[stops.stop_id.isin(stop_times_filtered.stop_id)]

        for _, stop in stops_filtered.iterrows():
            folium.CircleMarker(
                location=[stop.stop_lat, stop.stop_lon],
                radius=5,
                color=route_color,
                fill=True,
                fill_color=route_color,
                fill_opacity=0.9,
                popup=f"Stop: {stop.stop_name}"
            ).add_to(route_group)

def select_gtfs_folder():
    """Use argparse to get the GTFS folder path from command-line input."""
    parser = argparse.ArgumentParser(description="Load GTFS feeds from a specified folder.")
    parser.add_argument("folder", type=str, help="Path to the GTFS folder containing .zip files")
    args = parser.parse_args()
    return args.folder

if __name__ == "__main__":
    app = TransitMapApp()
    folder = "notebooks/Regional GTFS"

    if folder:
        app.load_gtfs(folder)
        app.display_routes()

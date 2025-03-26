import os
import folium
import gtfs_kit as gk
import pandas as pd
import argparse
from shapely.geometry import LineString
from folium.plugins import FeatureGroupSubGroup, TreeLayerControl

# Default center: Pittsburgh, PA
DEFAULT_CENTER = [40.4406, -79.9959]
MAX_ZOOM_LEVEL_FOR_STOPS = 14  # Define the maximum zoom level for displaying stops

class TransitMapApp:
    def __init__(self):
        self.gtfs_feeds = {}  # Stores all loaded GTFS feeds
        self.map = folium.Map(location=DEFAULT_CENTER, zoom_start=12)
        self.overlay_tree = {
            "label": "Agencies",
            "select_all_checkbox": "Un/select all",
            "children": []
        }  # Stores the tree structure for TreeLayerControl
        self.stop_markers = []  # Store stop markers for resizing

    def load_gtfs(self, folder_path):
        """Loads all GTFS feeds from the specified folder."""
        for filename in os.listdir(folder_path):
            if filename.endswith('.zip'):
                feed_path = os.path.join(folder_path, filename)
                try:
                    feed = gk.read_feed(feed_path, dist_units='km')
                    agency_name = feed.agency.agency_name.iloc[0] if not feed.agency.empty else filename
                    self.gtfs_feeds[agency_name] = feed
                    print(f"✅ Loaded GTFS feed: {agency_name}")
                except Exception as e:
                    print(f"❌ Error loading {filename}: {e}")

    def display_routes(self):
        """Displays all routes, grouped by agency, with proper collapsible subgroups."""
        print("🔍 Setting up agency groups...")
        
        for agency_name, feed in self.gtfs_feeds.items():
            print(f"📂 Creating collapsible group for {agency_name}")
            agency_group = {
                "label": agency_name,
                "select_all_checkbox": True,
                "children": []
            }
            
            routes = feed.routes
            shapes = feed.shapes
            trips = feed.trips
            stops = feed.stops
            stop_times = feed.stop_times

            for _, route in routes.iterrows():
                route_id = route.route_id
                route_name = route.route_long_name if pd.notna(route.route_long_name) else f"Route {route_id}"
                route_color = f"#{route.route_color}" if pd.notna(route.route_color) else "blue"
                
                route_desc = route.route_desc if 'route_desc' in route and pd.notna(route.route_desc) else 'N/A'

                route_info = (
                    f"<b>Route:</b> {route_name} ({route_id})<br>"
                    f"<b>Agency:</b> {agency_name}<br>"
                    f"<b>Route Type:</b> {route.route_type}<br>"
                    f"<b>Description:</b> {route_desc}"
                )

                print(f"  🚍 Adding route: {route_name} ({route_id})")
                route_group = {
                    "label": f"{route_name} ({route_id})",
                    "layer": folium.FeatureGroup(name=f"{route_name} ({route_id})").add_to(self.map)
                }

                # ---- GTFS Shape Line ----
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
                                popup=route_info
                            ).add_to(route_group["layer"])
                
                # ---- Display Stops ----
                self.display_stops(feed, route_id, route_color, route_group["layer"])

                agency_group["children"].append(route_group)

            self.overlay_tree["children"].append(agency_group)

        print("🛠 Adding TreeLayerControl with collapsible agency groups...")
        TreeLayerControl(overlay_tree=self.overlay_tree).add_to(self.map)

        # Add JS to dynamically resize stop circles based on zoom level
        folium.Map.add_child(self.map, folium.Element(
            f"""
            <script>
            var stopMarkers = {self.stop_markers};
            function resizeStopCircles() {{
                var zoom = map.getZoom();
                for (var i = 0; i < stopMarkers.length; i++) {{
                    var marker = stopMarkers[i];
                    var radius = zoom > {MAX_ZOOM_LEVEL_FOR_STOPS} ? 5 : 2;
                    marker.setRadius(radius);
                }}
            }}
            map.on('zoomend', resizeStopCircles);
            resizeStopCircles();
            </script>
            """
        ))
        
        self.map.save("transit_map.html")
        print("🗺️ Map updated: transit_map.html (open in browser)")

    def display_stops(self, feed, route_id, route_color, route_group):
        """Displays stops for the selected route with route-colored circles."""
        stops = feed.stops
        stop_times = feed.stop_times
        trips = feed.trips

        trip_ids = trips[trips.route_id == route_id].trip_id
        stop_times_filtered = stop_times[stop_times.trip_id.isin(trip_ids)]
        stops_filtered = stops[stops.stop_id.isin(stop_times_filtered.stop_id)]

        for _, stop in stops_filtered.iterrows():
            stop_url = stop.stop_url if 'stop_url' in stop and pd.notna(stop.stop_url) else None
            zone_id = stop.zone_id if 'zone_id' in stop and pd.notna(stop.zone_id) else 'N/A'
            
            stop_info = (
                f"<b>Stop:</b> {stop.stop_name}<br>"
                f"<b>Stop ID:</b> {stop.stop_id}<br>"
                f"<b>Location:</b> ({stop.stop_lat}, {stop.stop_lon})<br>"
                f"<b>Zone ID:</b> {zone_id}<br>"
                f"{'<b>Stop URL:</b> <a href=\'' + stop_url + '\' target=\'_blank\'>' + stop_url + '</a>' if stop_url else ''}"
            )

            popup = folium.Popup(stop_info, max_width=300)
            
            stop_marker = folium.CircleMarker(
                location=[stop.stop_lat, stop.stop_lon],
                radius=5,
                color=route_color,
                fill=True,
                fill_color=route_color,
                fill_opacity=0.9,
                popup=popup
            ).add_to(route_group)
            
            self.stop_markers.append(stop_marker.get_name())

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

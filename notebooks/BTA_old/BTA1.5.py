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
from datetime import datetime
from collections import defaultdict

class TransitPlanningTool:
    def __init__(self, gtfs_zip_path, ridership_csv_path):
        """Initialize the transit planning tool with GTFS and ridership data."""
        self.temp_dir = tempfile.mkdtemp()
        self.load_data(gtfs_zip_path, ridership_csv_path)
        self.calculate_metrics()
    
    def load_data(self, gtfs_zip_path, ridership_csv_path):
        """Load GTFS and ridership data."""
        # Extract GTFS files
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        
        # Load GTFS files
        self.routes = pd.read_csv(os.path.join(self.temp_dir, 'routes.txt'))
        self.stops = pd.read_csv(os.path.join(self.temp_dir, 'stops.txt'))
        self.trips = pd.read_csv(os.path.join(self.temp_dir, 'trips.txt'))
        self.stop_times = pd.read_csv(os.path.join(self.temp_dir, 'stop_times.txt'))
        self.shapes = pd.read_csv(os.path.join(self.temp_dir, 'shapes.txt'))
        
        # Load ridership data and ensure Ridership is numeric
        self.ridership = pd.read_csv(ridership_csv_path)
        self.ridership['Ridership'] = pd.to_numeric(self.ridership['Ridership'], errors='coerce').fillna(0)
    
    def parse_time(self, time_str):
        """Parse GTFS time string to datetime."""
        try:
            # Handle times past 24:00:00
            hours, minutes, seconds = map(int, time_str.split(':'))
            total_seconds = hours * 3600 + minutes * 60 + seconds
            normalized_seconds = total_seconds % 86400  # Normalize to 24-hour period
            normalized_hours = normalized_seconds // 3600
            normalized_minutes = (normalized_seconds % 3600) // 60
            normalized_seconds = normalized_seconds % 60
            return f"{normalized_hours:02d}:{normalized_minutes:02d}:{normalized_seconds:02d}"
        except:
            return None

    def calculate_metrics(self):
        """Calculate key transit service metrics."""
        self.calculate_frequencies()
        self.identify_transfers()
        self.calculate_coverage()
    
    def calculate_frequencies(self):
        """Calculate peak and off-peak frequencies by route."""
        self.frequencies = defaultdict(dict)
        
        peak_periods = [
            ('AM_Peak', '06:00:00', '09:00:00'),
            ('PM_Peak', '15:00:00', '18:00:00')
        ]
        
        for route_id in self.routes['route_id']:
            route_trips = self.trips[self.trips['route_id'] == route_id]
            
            for period, start, end in peak_periods:
                period_times = self.stop_times[
                    (self.stop_times['trip_id'].isin(route_trips['trip_id'])) &
                    (self.stop_times['arrival_time'] >= start) &
                    (self.stop_times['arrival_time'] <= end)
                ]
                
                if not period_times.empty:
                    stops = period_times['stop_id'].unique()
                    headways = []
                    
                    for stop in stops:
                        stop_times = period_times[period_times['stop_id'] == stop]['arrival_time']
                        if len(stop_times) > 1:
                            # Parse and sort times
                            parsed_times = [self.parse_time(t) for t in stop_times]
                            parsed_times = [t for t in parsed_times if t is not None]
                            if len(parsed_times) > 1:
                                times = pd.to_datetime(parsed_times, format='%H:%M:%S').sort_values()
                                headway = times.diff().mean().total_seconds() / 60
                                headways.append(headway)
                    
                    if headways:
                        self.frequencies[route_id][period] = np.mean(headways)
    
    def identify_transfers(self):
        """Identify transfer points between routes."""
        stop_routes = defaultdict(set)
        
        # Find routes serving each stop
        for _, row in self.trips.merge(self.stop_times, on='trip_id').iterrows():
            stop_routes[row['stop_id']].add(row['route_id'])
        
        # Find stops served by multiple routes
        self.transfers = []
        for stop_id, routes in stop_routes.items():
            if len(routes) > 1:
                stop_info = self.stops[self.stops['stop_id'] == stop_id].iloc[0]
                self.transfers.append({
                    'stop_id': stop_id,
                    'stop_name': stop_info['stop_name'],
                    'routes': list(routes),
                    'coordinates': [stop_info['stop_lat'], stop_info['stop_lon']]
                })
    
    def calculate_coverage(self):
        """Calculate 400m walking distance coverage."""
        # Create GeoDataFrame with explicit CRS
        self.stops_gdf = gpd.GeoDataFrame(
            self.stops, 
            geometry=[Point(xy) for xy in zip(self.stops['stop_lon'], self.stops['stop_lat'])],
            crs="EPSG:4326"
        )
        
        # Project to Web Mercator for consistent visualization
        self.stops_projected = self.stops_gdf.to_crs("EPSG:3857")
        
        # Create 400m buffers
        self.coverage = self.stops_projected.buffer(400)
        
        # Project back to WGS84 for Folium
        self.coverage = gpd.GeoSeries(self.coverage, crs="EPSG:3857").to_crs("EPSG:4326")
    
    def create_map(self, output_html_path):
        """Create interactive map with analysis layers."""
        # Create base map
        center_lat = self.stops['stop_lat'].mean()
        center_lon = self.stops['stop_lon'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
        
        # Add route layers
        self.add_routes(m)
        
        # Add stops with ridership
        self.add_stops(m)
        
        # Add transfer points
        self.add_transfers(m)
        
        # Add coverage area
        self.add_coverage(m)
        
        # Add legends and controls
        self.add_legends(m)
        folium.LayerControl().add_to(m)
        
        # Save map
        m.save(output_html_path)
    
    def add_routes(self, m):
        """Add route layers colored by frequency."""
        for route_id in self.routes['route_id']:
            shape_points = self.get_route_shape(route_id)
            if shape_points is not None:
                # Color based on AM peak frequency
                frequency = self.frequencies[route_id].get('AM_Peak', float('inf'))
                color = self.get_frequency_color(frequency)
                
                folium.PolyLine(
                    shape_points,
                    color=color,
                    weight=3,
                    opacity=0.7,
                    popup=f"Route {route_id}<br>Peak Frequency: {frequency:.1f} min",
                    name=f"Route {route_id}"
                ).add_to(m)
    
    def add_stops(self, m):
        """Add stops with ridership visualization."""
        for _, stop in self.ridership.iterrows():
            # Ensure ridership value is numeric and handle NaN/invalid values
            ridership = float(stop['Ridership']) if pd.notnull(stop['Ridership']) else 0
            radius = max(5, np.sqrt(ridership) * 0.5)  # Minimum radius of 5
            
            folium.CircleMarker(
                location=[float(stop['Latitude']), float(stop['Longitude'])],
                radius=radius,
                color='blue',
                fill=True,
                popup=f"Stop: {stop['Stop Name']}<br>Ridership: {int(ridership)}"
            ).add_to(m)
    
    def add_transfers(self, m):
        """Add transfer point markers."""
        for transfer in self.transfers:
            # Convert route IDs to strings before joining
            route_list = [str(route_id) for route_id in transfer['routes']]
            
            folium.CircleMarker(
                location=transfer['coordinates'],
                radius=8,
                color='purple',
                popup=f"Transfer Point<br>{transfer['stop_name']}<br>Routes: {', '.join(route_list)}",
                fill=True,
                fill_opacity=0.7
            ).add_to(m)
    
    def add_coverage(self, m):
        """Add service coverage area."""
        try:
            coverage_geojson = self.coverage.__geo_interface__
            folium.GeoJson(
                coverage_geojson,
                name="400m Walking Distance",
                style_function=lambda x: {
                    'fillColor': '#aaaaaa',
                    'fillOpacity': 0.2,
                    'color': '#888888',
                    'weight': 1
                }
            ).add_to(m)
        except Exception as e:
            print(f"Warning: Could not add coverage layer: {str(e)}")
    
    def add_legends(self, m):
        """Add map legends."""
        # Frequency legend
        legend_html = '''
            <div style="position: fixed; bottom: 50px; left: 50px; background: white; padding: 10px; border: 2px solid grey;">
            <h4>Service Frequency</h4>
            <p><span style="color: #1a9850">●</span> High (≤10 min)</p>
            <p><span style="color: #fed976">●</span> Medium (10-20 min)</p>
            <p><span style="color: #d73027">●</span> Low (>20 min)</p>
            </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
    
    def get_route_shape(self, route_id):
        """Get shape points for a route."""
        route_trips = self.trips[self.trips['route_id'] == route_id]
        if route_trips.empty:
            return None
        
        shape_id = route_trips.iloc[0]['shape_id']
        shape_points = self.shapes[self.shapes['shape_id'] == shape_id].sort_values('shape_pt_sequence')
        
        if shape_points.empty:
            return None
        
        return [[row.shape_pt_lat, row.shape_pt_lon] for _, row in shape_points.iterrows()]
    
    @staticmethod
    def get_frequency_color(frequency):
        """Return color based on service frequency."""
        if frequency <= 10:
            return '#1a9850'  # High frequency
        elif frequency <= 20:
            return '#fed976'  # Medium frequency
        else:
            return '#d73027'  # Low frequency

# Example usage
if __name__ == "__main__":
    planner = TransitPlanningTool("notebooks/google_transit.zip", "notebooks/Master.csv")
    planner.create_map("transit_analysis.html")
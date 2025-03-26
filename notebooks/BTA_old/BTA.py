import pandas as pd
import folium
import zipfile
import tempfile
import os
from collections import defaultdict
import numpy as np

class TransitPlanningTool:
    def __init__(self, gtfs_zip_path, ridership_csv_path):
        """Initialize the transit planning tool with GTFS and ridership data."""
        self.temp_dir = tempfile.mkdtemp()
        self.load_data(gtfs_zip_path, ridership_csv_path)
        self.calculate_metrics()
        
        # Define distinct colors for routes
        self.route_colors = {
            'red': '#FF0000',
            'blue': '#0000FF',
            'green': '#008000',
            'purple': '#800080',
            'orange': '#FFA500',
            'brown': '#A52A2A',
            'pink': '#FFC0CB',
            'gold': '#FFD700',
            'teal': '#008080',
            'indigo': '#4B0082'
        }
        # Assign colors to routes
        self.assign_route_colors()
    
    def load_data(self, gtfs_zip_path, ridership_csv_path):
        """Load GTFS and ridership data."""
        with zipfile.ZipFile(gtfs_zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        
        self.routes = pd.read_csv(os.path.join(self.temp_dir, 'routes.txt'))
        self.stops = pd.read_csv(os.path.join(self.temp_dir, 'stops.txt'))
        self.trips = pd.read_csv(os.path.join(self.temp_dir, 'trips.txt'))
        self.stop_times = pd.read_csv(os.path.join(self.temp_dir, 'stop_times.txt'))
        self.shapes = pd.read_csv(os.path.join(self.temp_dir, 'shapes.txt'))
        
        self.ridership = pd.read_csv(ridership_csv_path)
        self.ridership['Ridership'] = pd.to_numeric(self.ridership['Ridership'], errors='coerce').fillna(0)
    
    def assign_route_colors(self):
        """Assign unique colors to each route."""
        self.route_to_color = {}
        available_colors = list(self.route_colors.values())
        
        for i, route_id in enumerate(self.routes['route_id']):
            color_index = i % len(available_colors)
            self.route_to_color[str(route_id)] = available_colors[color_index]
    
    def calculate_metrics(self):
        """Calculate key transit service metrics."""
        self.identify_transfers()
        self.calculate_transfer_ridership()
    
    def identify_transfers(self):
        """Identify transfer points between routes."""
        stop_routes = defaultdict(set)
        
        # Find routes serving each stop
        for _, row in self.trips.merge(self.stop_times, on='trip_id').iterrows():
            stop_routes[row['stop_id']].add(str(row['route_id']))
        
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
    
    def calculate_transfer_ridership(self):
        """Calculate combined ridership for transfer points."""
        for transfer in self.transfers:
            total_ridership = 0
            for route in transfer['routes']:
                route_ridership = self.ridership[
                    (self.ridership['Route'].astype(str) == route) & 
                    (self.ridership['Stop ID'] == transfer['stop_id'])
                ]['Ridership'].sum()
                total_ridership += route_ridership
            transfer['total_ridership'] = total_ridership
    
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
    
    def create_map(self, output_html_path, selected_routes=None):
        """Create interactive map with selected routes."""
        # If no routes specified, use all routes
        if selected_routes is None:
            selected_routes = [str(route_id) for route_id in self.routes['route_id']]
        else:
            selected_routes = [str(route_id) for route_id in selected_routes]
        
        # Create base map
        center_lat = self.stops['stop_lat'].mean()
        center_lon = self.stops['stop_lon'].mean()
        m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
        
        # Add selected routes
        self.add_routes(m, selected_routes)
        
        # Add stops with ridership
        self.add_stops(m, selected_routes)
        
        # Add transfer points
        self.add_transfers(m, selected_routes)
        
        # Add layer control
        folium.LayerControl().add_to(m)
        
        # Save map
        m.save(output_html_path)
    
    def add_routes(self, m, selected_routes):
        """Add selected route layers."""
        for route_id in selected_routes:
            shape_points = self.get_route_shape(route_id)
            if shape_points is not None:
                color = self.route_to_color[str(route_id)]
                
                folium.PolyLine(
                    shape_points,
                    color=color,
                    weight=3,
                    opacity=0.7,
                    popup=f"Route {route_id}",
                    name=f"Route {route_id}"
                ).add_to(m)
    
    def add_stops(self, m, selected_routes):
        """Add stops for selected routes."""
        for _, stop in self.ridership[self.ridership['Route'].astype(str).isin(selected_routes)].iterrows():
            ridership = float(stop['Ridership']) if pd.notnull(stop['Ridership']) else 0
            radius = max(5, np.sqrt(ridership) * 0.5)
            color = self.route_to_color[str(stop['Route'])]
            
            folium.CircleMarker(
                location=[float(stop['Latitude']), float(stop['Longitude'])],
                radius=radius,
                color=color,
                fill=True,
                popup=f"Stop: {stop['Stop Name']}<br>Ridership: {int(ridership)}"
            ).add_to(m)
    
    def add_transfers(self, m, selected_routes):
        """Add transfer points for selected routes."""
        for transfer in self.transfers:
            # Only show transfers that connect selected routes
            transfer_routes = [route for route in transfer['routes'] if route in selected_routes]
            if len(transfer_routes) > 1:
                # Calculate size based on total ridership
                radius = max(8, np.sqrt(transfer['total_ridership']) * 0.3)
                
                # Create gradient color from route colors
                colors = [self.route_to_color[route] for route in transfer_routes]
                gradient = {
                    'color': colors[0],
                    'fillColor': colors[-1]
                }
                
                # Create popup with route information
                route_info = "<br>".join([
                    f"Route {route}: {self.route_to_color[route]}"
                    for route in transfer_routes
                ])
                popup_text = f"""
                Transfer Point<br>
                {transfer['stop_name']}<br>
                Total Ridership: {int(transfer['total_ridership'])}<br>
                Routes:<br>{route_info}
                """
                
                folium.CircleMarker(
                    location=transfer['coordinates'],
                    radius=radius,
                    color=gradient['color'],
                    fill=True,
                    fill_color=gradient['fillColor'],
                    fill_opacity=0.7,
                    popup=popup_text
                ).add_to(m)

# Example usage
if __name__ == "__main__":
    planner = TransitPlanningTool("notebooks/google_transit.zip", "notebooks/Master.csv")
    
    # Create map with all routes
    planner.create_map("all_routes_map.html")
    
    # Create map with selected routes only
    selected_routes = ['1', '2', '3']  # Replace with actual route IDs
    planner.create_map("selected_routes_map.html", selected_routes)
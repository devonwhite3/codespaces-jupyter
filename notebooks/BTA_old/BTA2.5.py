import pandas as pd
import folium
from folium import plugins
import branca.colormap as cm
import numpy as np
from pathlib import Path

def load_and_process_ridership(ridership_file):
    """Load and process ridership data from CSV file."""
    df = pd.read_csv(ridership_file)
    
    # Calculate route-level statistics
    route_stats = df.groupby('Route')['Ridership'].agg(['sum', 'mean', 'count']).reset_index()
    route_stats.columns = ['Route', 'Total_Ridership', 'Avg_Ridership', 'Stop_Count']
    
    # Group by stop location to get total ridership
    stop_ridership = df.groupby(['Stop', 'Lat', 'Lon', 'Name', 'Route'])['Ridership'].sum().reset_index()
    
    return stop_ridership, route_stats

def create_ridership_map(stop_ridership, route_stats, output_file='transit_map.html'):
    """Create an interactive map showing ridership patterns."""
    # Create base map centered on average coordinates
    center_lat = stop_ridership['Lat'].mean()
    center_lon = stop_ridership['Lon'].mean()
    m = folium.Map(location=[center_lat, center_lon], 
                  zoom_start=12,
                  tiles='cartodbpositron')
    
    # Create color scale for ridership
    max_riders = stop_ridership['Ridership'].max()
    colormap = cm.LinearColormap(
        colors=['yellow', 'orange', 'red'],
        vmin=0,
        vmax=max_riders,
        caption='Daily Ridership'
    )
    m.add_child(colormap)
    
    # Create route groups for organization
    route_groups = {}
    for route in stop_ridership['Route'].unique():
        route_groups[f"Route {route}"] = folium.FeatureGroup(name=f"Route {route}")
    
    # Add stops with ridership bubbles, organized by route
    for _, row in stop_ridership.iterrows():
        route_group = route_groups[f"Route {row['Route']}"]
        folium.CircleMarker(
            location=[row['Lat'], row['Lon']],
            radius=np.sqrt(row['Ridership']) / 2,  # Scale bubble size
            popup=(f"Stop: {row['Name']}<br>"
                  f"Route: {row['Route']}<br>"
                  f"Ridership: {row['Ridership']}"),
            color='blue',
            fill=True,
            fill_color=colormap(row['Ridership']),
            fill_opacity=0.7
        ).add_to(route_group)
    
    # Add all route groups to map
    for group in route_groups.values():
        group.add_to(m)
    
    # Add heatmap layer
    heat_data = [[row['Lat'], row['Lon'], row['Ridership']] 
                 for _, row in stop_ridership.iterrows()]
    heatmap_group = folium.FeatureGroup(name="Heatmap")
    plugins.HeatMap(heat_data).add_to(heatmap_group)
    heatmap_group.add_to(m)
    
    # Add route statistics to map
    stats_html = "<h4>Route Statistics</h4>"
    stats_html += "<table>"
    stats_html += "<tr><th>Route</th><th>Total Ridership</th><th>Avg per Stop</th><th>Stops</th></tr>"
    for _, row in route_stats.iterrows():
        stats_html += (f"<tr><td>{row['Route']}</td>"
                      f"<td>{int(row['Total_Ridership']):,}</td>"
                      f"<td>{int(row['Avg_Ridership']):,}</td>"
                      f"<td>{int(row['Stop_Count'])}</td></tr>")
    stats_html += "</table>"
    
    stats_group = folium.FeatureGroup(name="Route Statistics")
    stats_element = folium.Element(stats_html)
    m.get_root().html.add_child(stats_element)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Save map
    m.save(output_file)
    return m

def main(ridership_file):
    """Main function to create transit ridership visualization."""
    # Load and process data
    stop_ridership, route_stats = load_and_process_ridership(ridership_file)
    
    # Create visualization
    create_ridership_map(stop_ridership, route_stats)
    
    # Print summary statistics
    print("\nRoute Statistics:")
    print(route_stats.to_string(index=False))
    
if __name__ == "__main__":
    ridership_file = "notebooks/ridership.csv"
    main(ridership_file)
import gtfs_kit as gk
import networkx as nx
import geopandas as gpd
import shapely.geometry
import pandas as pd
import os
from datetime import datetime

def load_gtfs_from_folder(folder_path):
    feeds = []
    for file_name in os.listdir(folder_path):
        if file_name.endswith('.zip'):
            feed_path = os.path.join(folder_path, file_name)
            feed = gk.read_feed(feed_path, dist_units='km')
            feeds.append(feed)
    return feeds

def merge_schedules(feeds):
    merged_schedule = feeds[0]
    for feed in feeds[1:]:
        merged_schedule.stops = pd.concat([merged_schedule.stops, feed.stops])
        merged_schedule.trips = pd.concat([merged_schedule.trips, feed.trips])
        merged_schedule.stop_times = pd.concat([merged_schedule.stop_times, feed.stop_times])
        merged_schedule.routes = pd.concat([merged_schedule.routes, feed.routes])
        merged_schedule.calendar = pd.concat([merged_schedule.calendar, feed.calendar])
    return merged_schedule

def parse_time(time_str):
    return datetime.strptime(time_str, '%H:%M:%S').time()

def create_network(schedule):
    graph = nx.DiGraph()
    for trip in schedule.trips.itertuples():
        trip_stops = schedule.stop_times[schedule.stop_times.trip_id == trip.trip_id]
        trip_stops = trip_stops.sort_values(by='stop_sequence')
        for i in range(len(trip_stops) - 1):
            stop_from = trip_stops.iloc[i]
            stop_to = trip_stops.iloc[i + 1]
            departure_time = parse_time(stop_from.departure_time)
            arrival_time = parse_time(stop_to.arrival_time)
            travel_time = (datetime.combine(datetime.min, arrival_time) - datetime.combine(datetime.min, departure_time)).total_seconds() / 60
            if travel_time > 0:
                graph.add_edge(stop_from.stop_id, stop_to.stop_id, weight=travel_time)
    return graph

def calculate_isochrone(graph, origin, travel_time):
    isochrone = nx.single_source_dijkstra_path_length(graph, origin, cutoff=travel_time)
    return isochrone

def visualize_isochrone(isochrone, schedule):
    stops = schedule.stops.set_index('stop_id')
    gdf = gpd.GeoDataFrame(stops, geometry=gpd.points_from_xy(stops.stop_lon, stops.stop_lat))
    isochrone_stops = gdf[gdf.index.isin(isochrone.keys())]
    return isochrone_stops

# Example usage
folder_path = 'notebooks/Regional GTFS copy'
feeds = load_gtfs_from_folder(folder_path)
combined_schedule = merge_schedules(feeds)
network = create_network(combined_schedule)
origin = 'your_origin_stop_id'
travel_time = 30  # minutes

isochrone = calculate_isochrone(network, origin, travel_time)
isochrone_stops = visualize_isochrone(isochrone, combined_schedule)

print(isochrone_stops)

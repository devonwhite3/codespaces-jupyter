import sqlite3
import zipfile
import os
import pandas as pd
import heapq
from pathlib import Path
import argparse
from fastapi import FastAPI

app = FastAPI()

class GTFSProcessor:
    def __init__(self, db_path="gtfs_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

    def _create_tables(self):
        """Create necessary tables for GTFS data storage."""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT,
            stop_lat REAL,
            stop_lon REAL
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS routes (
            route_id TEXT PRIMARY KEY,
            route_short_name TEXT,
            route_long_name TEXT
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS trips (
            trip_id TEXT PRIMARY KEY,
            route_id TEXT,
            service_id TEXT,
            FOREIGN KEY(route_id) REFERENCES routes(route_id)
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS stop_times (
            trip_id TEXT,
            arrival_time TEXT,
            departure_time TEXT,
            stop_id TEXT,
            stop_sequence INTEGER,
            FOREIGN KEY(trip_id) REFERENCES trips(trip_id),
            FOREIGN KEY(stop_id) REFERENCES stops(stop_id)
        )
        """)
        self.conn.commit()

    def import_gtfs(self, zip_path):
        """Extracts GTFS data from a zip file and loads it into the database."""
        extract_path = Path("temp_gtfs")
        extract_path.mkdir(parents=True, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extractall(extract_path)
        
        self._load_data_to_db(extract_path)
        
        for file in extract_path.glob("*"):
            file.unlink()
        extract_path.rmdir()

    def _load_data_to_db(self, folder):
        """Loads relevant GTFS CSV files into the database."""
        stops_df = pd.read_csv(folder / "stops.txt")
        stops_df.to_sql("stops", self.conn, if_exists="replace", index=False)
        
        routes_df = pd.read_csv(folder / "routes.txt")
        routes_df.to_sql("routes", self.conn, if_exists="replace", index=False)
        
        trips_df = pd.read_csv(folder / "trips.txt")
        trips_df.to_sql("trips", self.conn, if_exists="replace", index=False)
        
        stop_times_df = pd.read_csv(folder / "stop_times.txt")
        stop_times_df.to_sql("stop_times", self.conn, if_exists="replace", index=False)

    def find_shortest_path(self, origin, destination, time):
        """Finds the shortest transit route using Dijkstra's Algorithm."""
        query = """
        SELECT trip_id, stop_id, departure_time, stop_sequence FROM stop_times
        WHERE departure_time >= ?
        ORDER BY departure_time;
        """
        self.cursor.execute(query, (time,))
        stops = self.cursor.fetchall()
        graph = {}

        for trip_id, stop_id, departure_time, stop_sequence in stops:
            if stop_id not in graph:
                graph[stop_id] = []
            graph[stop_id].append((trip_id, departure_time, stop_sequence))

        heap = [(0, origin, [])]  # (cost, current_stop, path)
        visited = set()

        while heap:
            cost, current, path = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)
            path = path + [current]
            if current == destination:
                return path

            for trip_id, departure_time, stop_sequence in graph.get(current, []):
                heapq.heappush(heap, (cost + 1, trip_id, path))

        return None

    def query_trip(self, origin, destination, time):
        """Finds an optimal route from origin to destination at the given time."""
        path = self.find_shortest_path(origin, destination, time)
        return path if path else "No available route found."

@app.get("/trip/")
def get_trip(origin: str, destination: str, time: str):
    processor = GTFSProcessor()
    trip = processor.query_trip(origin, destination, time)
    return {"route": trip}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GTFS Trip Planner")
    parser.add_argument("--import-gtfs", type=str, help="Path to GTFS zip file")
    parser.add_argument("--query", nargs=3, metavar=("origin", "destination", "time"), help="Find a trip")
    
    args = parser.parse_args()
    processor = GTFSProcessor()
    
    if args.import_gtfs:
        processor.import_gtfs(args.import_gtfs)
    
    if args.query:
        origin, destination, time = args.query
        trip = processor.query_trip(origin, destination, time)
        print("Best Trip:", trip)

from flask import Flask, request, jsonify, render_template
import requests
import folium
import openrouteservice
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# OpenRouteService API Key (Get a free key at https://openrouteservice.org/sign-up/)
ORS_API_KEY = "your_openrouteservice_api_key"
ors_client = openrouteservice.Client(key=ORS_API_KEY)

# Function to fetch nearby places from OpenStreetMap (No API Key required)
def get_nearby_places(lat, lon, amenity, radius=5000):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={amenity}&bounded=1&limit=5&lat={lat}&lon={lon}&radius={radius}"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise error if bad response

        places_data = response.json()
        if not places_data:
            return []

        return [(float(place["lat"]), float(place["lon"])) for place in places_data]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching places: {e}")
        return []

# Function to get maximum travel time to amenities
def get_max_travel_time(user_location, amenities, mode="driving-car"):
    max_time = 0
    for amenity in amenities:
        coords = [user_location, amenity]
        try:
            route = ors_client.directions(coords, profile=mode, format="geojson")
            travel_time = route['features'][0]['properties']['segments'][0]['duration'] / 60  # Convert to minutes
            max_time = max(max_time, travel_time)
        except Exception as e:
            print(f"Error fetching travel time: {e}")
            continue
    return max_time

@app.route("/update_location", methods=["POST"])
def update_location():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400

        lat = data.get("lat")
        lon = data.get("lon")
        if lat is None or lon is None:
            return jsonify({"error": "Latitude and longitude are required"}), 400

        mode = data.get("mode", "driving-car")
        amenity_type = data.get("amenity_type", "restaurant")

        amenities = get_nearby_places(lat, lon, amenity_type)
        max_travel_time = get_max_travel_time([lon, lat], amenities, mode)

        return jsonify({"max_travel_time": max_travel_time, "amenities": amenities})

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

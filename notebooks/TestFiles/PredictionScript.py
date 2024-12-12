# %%
from flask import Flask, jsonify
import requests

#API Request
response = requests.get("https://realtime.portauthority.org/bustime/api/v3/getpredictions?key=QK3n4Cr23BURNkfRyWBC2HQS6&rtpidatafeed=Light%20Rail&stpid=99904&format=json")
#Format API Request
data = response.json()
try:
    data = response.json()
    bustimeResponse = data['bustime-response']['prd']
    for x in range(0,len(bustimeResponse)):
        #Pull First Arrival Prediction Data
        data = bustimeResponse[x]
        route = data['rt']
        predictionCountdown = data['prdctdn']
        print(route + "   " + predictionCountdown)
except:
    print("No Arrival Times")




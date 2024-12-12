from flask import Flask, request
# from StopMonitoringScript import StopMonitor
import requests


app = Flask(__name__)

BUSTIME_API_KEY = "QK3n4Cr23BURNkfRyWBC2HQS6"
stop = "99904"
#max_visits = request.args.get('max_visits', 2)
max_visits = 2
AgencyId = "Light%20Rail"

@app.route("/")
def stop_monitor():
    #API Request
    response = requests.get("https://realtime.portauthority.org/bustime/api/v3/getpredictions?key=QK3n4Cr23BURNkfRyWBC2HQS6&rtpidatafeed=Light%20Rail&stpid=99904&format=json")
    #Format API Request
    try:
        data = response.json()
        bustimeResponse = data['bustime-response']['prd']
        return bustimeResponse
        routes = []
        predictionCountdowns = []
        bustimeResponse = data['bustime-response']['prd']
        for x in range(0,len(bustimeResponse)):
            #Pull First Arrival Prediction Data
            data = bustimeResponse[x]
            route = data['rt']
            routes.append(route)
            predictionCountdown = data['prdctdn']
            predictionCountdowns.append(predictionCountdown)
            # return (route + "   " + predictionCountdown)

    except:
        return ("No Arrival Times")
    
    countdownString = ""
    for y in range(len(routes)):
        countdownString = countdownString + f"{routes[y]}   {predictionCountdowns[y]}"
    
    return countdownString

if __name__ == "__main__":
    app.run(debug=True)
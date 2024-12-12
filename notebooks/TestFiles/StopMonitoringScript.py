# %%
#!/usr/bin/env python
import requests
import json
import jsonpickle

"""
Query the PRT BusTime stop monitoring endpoint for bus information.

Example calls:
# SLVR_BonAir_as_String = StopMonitor(MY_API_KEY, '99904', 'SLVR', 2)
# AllRoutes_BonAir_as_endpoint = https://realtime.portauthority.org/bustime/api/v3/getpredictions?key=QK3n4Cr23BURNkfRyWBC2HQS6&rtpidatafeed=Light%20Rail&stpid=99904&format=json
"""

#STOP_MONITORING_ENDPOINT = "https://realtime.portauthority.org/bustime/api/v3/getpredictions?key="
# VEHICLE_MONITORING_ENDPOINT = "http://bustime.mta.info/api/siri/vehicle-monitoring.json"

# FEET_PER_METER = 3.28084
# FEET_PER_MILE = 5280

class StopMonitor(object):

  def __init__(self, api_key, stop_id, AgencyId, max_visits=3):
     self.stop_id = stop_id
     self.max_visits = max_visits
     self.AgencyId = AgencyId
     # TODO what if the request throws an exception?
     self.visits = self.stop_monitoring_request()
     self.name = self.visits[0].stpnm if len(self.visits) >0 else None
  def bustime_request_json(self):
        #TODO define num_visits globally (or per instance of this class)
        #line_id = "MTA NYCT_%s" % self.line
        #TODO populate these better to account for null values (see self.line above)
        blob = {
        'key': self.api_key,
        'OperatorRef': self.AgencyId,
        'MonitoringRef': self.stop_id,
        # 'LineRef': line_id,
        'MaximumStopVisits': self.max_visits,
        }
        return blob
  def stop_monitoring_request(self):
    blob = {
      'key': self.api_key,
      'OperatorRef': self.AgencyId,
      'MonitoringRef': self.stop_id,
      'MaximumStopVisits': self.max_visits
    }
    payload = blob
    response = requests.get("https://realtime.portauthority.org/bustime/api/v3/getpredictions?key=" + payload.key + "&rtpidatafeed=" + payload.OperatorRef + "&stpid=" + payload.MonitoringRef + "&format=json")
    return self.parse_bustime_response(response.json())
  def parse_bustime_response(self, rsp):
    # self.updated_at
    parsed_visits = []
    visits_json = rsp['bustime-response']['prd']
    for raw_visit in visits_json:
      parsed_visits.append(Visit(raw_visit))
    return parsed_visits
  def __str__(self):
    output = []
    if self.name:
      output.append("{}:".format(self.name))
    for visit in self.visits:
      output.append("{}. {}".format(self.visits.index(visit)+1, visit))
    if len(self.visits) == 0:
      output.append("no buses are on the way. sad :(")
    return '\n'.join(output)
  def json(self):
    return jsonpickle.encode(self.visits)

class Visit(object):

  def __init__(self, raw_visit):
    response = raw_visit['bustime-response']['prd]']
    self.route = response['rt']
    # call = raw_visit['MonitoredVehicleJourney']['MonitoredCall']
    # distances = call['Extensions']['Distances']
    self.monitored_stop = response['stpnm']
    # self.stops_away = distances['StopsFromCall']
    #self.distance = round(distances['DistanceFromCall'] * FEET_PER_METER / FEET_PER_MILE, 2)
    self.prediction = response['prdctdn']
  def __str__(self):
    return ("{} bus {} stops away ({} miles)").format(
          self.route, self.stops_away, self.distance)
  def __getstate__(self):
    return json.dumps({
      'route': self.route,
      'stops_away': self.stops_away,
      'distance': self.distance,
    })

# %%




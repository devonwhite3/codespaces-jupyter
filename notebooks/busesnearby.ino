/*

BusesNearby - A real-time bus stop monitor for New York City Transit buses
using the MTA's BusTime API. Requires the BusesNearby Flask app in order
to receive data.

Copyright (c) Ian D. Westcott, 2014

Distributed under a Simplified BSD License. TL;DR:
Redistribution and use in source and binary forms, with or without
modification, are permitted. Provided as-is, no warranties, liabilities, etc.

This software requires the following libraries:

* ArduinoJsonParser:
  https://github.com/bblanchon/ArduinoJsonParser

* Adafruit CC3000 Library:
  https://github.com/adafruit/Adafruit_CC3000_Library

* Adafruit HT1632 Library:
  https://github.com/adafruit/HT1632

Parts of this code were derived from Adafruit's various tutorials for the
components used, available via the above links. Adafruit invests time and
resources providing this open source code, please support Adafruit and
open-source hardware by purchasing products from Adafruit!

*/

#include "HT1632.h"
#include <Adafruit_CC3000.h>

#include <ccspi.h>
#include <SPI.h>
#include <string.h>

#include <JsonParser.h>
#include "utility/debug.h"

// Pins for the LED display
#define MATRIX_DATA 2
#define MATRIX_WR   6
#define MATRIX_CS   4

// Pins for the wifi breakout
#define ADAFRUIT_CC3000_IRQ   3
#define ADAFRUIT_CC3000_VBAT  5
#define ADAFRUIT_CC3000_CS    10

// Instantiate the LED matrix controller
HT1632LEDMatrix matrix = HT1632LEDMatrix(MATRIX_DATA, MATRIX_WR, MATRIX_CS);

// Instantiate the wifi breakout controller
Adafruit_CC3000 cc3000 = Adafruit_CC3000(ADAFRUIT_CC3000_CS, ADAFRUIT_CC3000_IRQ, ADAFRUIT_CC3000_VBAT,
                                         SPI_CLOCK_DIVIDER);

// What network to connect to
#define WLAN_SSID       "My Wireless" // you probably want to change this
#define WLAN_PASS       "mywirelesspassword" // and this too
// Security can be WLAN_SEC_UNSEC, WLAN_SEC_WEP, WLAN_SEC_WPA or WLAN_SEC_WPA2
#define WLAN_SECURITY   WLAN_SEC_WPA2

#define IDLE_TIMEOUT_MS  3000

// Hostname of the Flask app. Use this if it's hosted somewhere official
#define BUSESNEARBY_SITE  "example.com"
#define BUSESNEARBY_PAGE  "/"

#define STOP_ID       "308100" // Find your stop at http://bustime.mta.info/
#define ROUTE_ID      "B70"
#define MAX_VISITS    "2"

#define REFRESH_RATE   30 // seconds

#define PHOTOCELL_PIN  0  // the cell and 10K pulldown are connected to a0

int photocellReading;     // the analog reading from the sensor divider
int matrixBrightness;

// NOTE: If not using a hostname, the IP has to be defined manually in
// the getBusInfo() function below
uint32_t server_ip;

char busTimeResponse[320];
uint8_t timer = 0;

void setup() {
}

void loop(void)
}

/* Adjust the display brightness using the attached photocell */
void adjustBrightness()
}


/* Print a cute bus icon */
void busIcon(uint8_t startx, uint8_t starty)
}

/* Print an arrow (not currently used) */
void drawArrow(uint8_t startx, uint8_t starty)
}

/* Print some text on the LED screen (up to 8 characters) */
void printLEDText(char text[9])
}

/* Print the number of stops, right-aligned on the specified line */
void printStopsAway(char text[5], int line)
}

/* Initialize the wifi breakout and connect to the network */
void startWifi(void)
}

/* Connect to the API endpoint and download the bus info JSON */
bool getBusInfo(void)
{
  // Use this if the Flask app is hosted somewhere with a hostname
  // Try looking up the website's IP address
  // Serial.print(BUSESNEARBY_SITE); Serial.print(F(" -> "));
  // while (server_ip == 0) {
  //   if (! cc3000.getHostByName(BUSESNEARBY_SITE, &server_ip)) {
  //     Serial.println(F("\nCouldn't resolve!"));
  //     return false;
  //   }
  //   delay(500);
  // }

  // Comment this out if using the hostname lookup code above
  server_ip = cc3000.IP2U32(192, 168, 5, 50);
  // the port of the flask app. Set to 80 if hosted somewhere official
  int server_port = 5000;

  Serial.print("\nAttempting to connect to "); Serial.print(server_ip); Serial.print("\n");

  // Try connecting to the site
  Adafruit_CC3000_Client www = cc3000.connectTCP(server_ip, server_port);
  if (www.connected()) {
    Serial.print("\nConnected, sending request...");
    www.fastrprint(F("GET "));
    www.fastrprint(F("/")); www.fastrprint(F("?"));
    www.fastrprint(F("stop=")); www.fastrprint(STOP_ID);
    www.fastrprint(F("&route=")); www.fastrprint(ROUTE_ID);
    //www.fastrprint(F("&max_visits=")); www.fastrprint(MAX_VISITS);
    www.fastrprint(F(" HTTP/1.1\r\n"));
    www.fastrprint(F("Host: ")); www.fastrprint(F("192.168.5.50")); www.fastrprint(F("\r\n"));
    www.fastrprint(F("\r\n"));
    www.println();
  } else {
    Serial.println(F("Connection to bus info endpoint failed!"));
    return false;
  }

  /* Read data until the connecion is closed or the idle timeout is reached. */
  uint16_t i = 0;
  unsigned long lastRead = millis();
  bool store_stream = false;

  Serial.println(F("\nReading data stream:"));
  while (www.connected() && (millis() - lastRead < IDLE_TIMEOUT_MS)) {
    while (www.available()) {
      char c = www.read();
      // only start saving data after we see the opening JSON bracket
      if (c == '[') {
        store_stream = true;
      }
      if (store_stream) {
        Serial.print(c);
        busTimeResponse[i] = c;
        i = i + 1;
      }
      lastRead = millis();
    }
  }

  // make sure our new contents are properly terminated
  busTimeResponse[i] = '\0';

  www.close();

  // how are we doing memory-wise?
  Serial.print("\n\nFree RAM: "); Serial.println(getFreeRam(), DEC);
  Serial.print("\nBusTime response size is "); Serial.print(i);
  Serial.println(F("\nBusTime response data is "));
  Serial.print(busTimeResponse);

  return true;
}

bool parseBusJSON(void)
{
  JsonParser<32> parser;

  JsonArray array = parser.parseArray(busTimeResponse);

  matrix.clearScreen();

  if (!array.success())
  {
      Serial.println("\nCouldn't parse BusTime response!");
      return false;
  }

  for (int i = 0; i < array.getLength(); i++)
  {
    JsonHashTable busInfo = array.getHashTable(i);
    if (!busInfo.success())
    {
        Serial.println("\nCouldn't parse bus info!");
        return false;
    }
    char* stops_away = busInfo.getString("stops_away");
    Serial.print("\nStops Away: "); Serial.print(stops_away);

    busIcon(0, 8 * i);
    printStopsAway(stops_away, i);
  }
  return true;
}
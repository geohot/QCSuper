#!/usr/bin/python3
#-*- encoding: Utf-8 -*-
from protocol.gsmtap import build_gsmtap_ip
from protocol.log_types import *
from struct import pack, unpack
from base64 import b64encode
from subprocess import run
from json import dumps
from time import time

from protocol.subsystems import *
from protocol.messages import *

from modules._enable_log_mixin import EnableLogMixin, TYPES_FOR_RAW_PACKET_LOGGING

"""
    This module registers various diag LOG events, and generates a JSON file
    with both GPS location from the Android ADB, and raw LOG diag frames.
    
    It produces raw output deemed for off-line reuse by another module.
    
    Format:
    {"lat": 49.52531, "lng": 2.17493, "timestamp": 1521834122.2525692}
    {"log_type": 0xb0e2, "log_frame": "[base64 encoded]", "timestamp": 1521834122.2525692}
    
    This module is meant to be used with the "ADB" input.
"""

DELAY_CHECK_GEOLOCATION = 1 # Check GPS location every 10 seconds

CGPS_DIAG_PDAPI_CMD = 100
CGPS_OEM_CONTROL = 202
GPSDIAG_OEMFEATURE_DRE = 1
GPSDIAG_OEM_DRE_ON = 1

class JsonGeoDumper(EnableLogMixin):
    
    def __init__(self, diag_input, json_geo_file):
        
        self.json_geo_file = json_geo_file
        
        self.diag_input = diag_input
        
        self.limit_registered_logs = TYPES_FOR_RAW_PACKET_LOGGING
        
        self.last_time_geolocation_was_checked = 0
        self.lat, self.lng = None, None

    def on_init_nope(self):
        print("on init super")
        super().on_init()
        print("on init")
        opcode, payload = self.diag_input.send_recv(DIAG_SUBSYS_CMD_F, pack('<BHBBIIII',
          DIAG_SUBSYS_GPS,
          CGPS_DIAG_PDAPI_CMD,
          CGPS_OEM_CONTROL,
          1,
          GPSDIAG_OEMFEATURE_DRE,
          GPSDIAG_OEM_DRE_ON,
          0,0
        )
        , accept_error = False)
        print(opcode, payload)
    
    def on_log(self, log_type, log_payload, log_header, timestamp = 0):
        print("on_log %x" % log_type, len(log_payload), log_header, timestamp)

        if log_type == 0x1477:
          #from hexdump import hexdump
          #hexdump(log_payload)
          dat = unpack("<BIHIffffB", log_payload[0:28])
          print(dat)
          sats = log_payload[28:]
          print(len(sats), len(sats)/dat[-1])
          L = 70
          for i in range(dat[-1]):
            sat = unpack("<BbBBBBBHhBHIffffIBIffiHffBI", sats[L*i:L*i+L])
            print("  ", sat)
        if log_type == 0x1480:
          print("glonass")
        if log_type == 0x1756:
          print("beidou")
        if log_type == 0x1886:
          print("gal")
        
        if hasattr(self.diag_input, 'get_gps_location'):
            
            if self.last_time_geolocation_was_checked < time() - DELAY_CHECK_GEOLOCATION:
                
                lat, lng = self.diag_input.get_gps_location()
                
                if lat and lng and (lat, lng) != (self.lat, self.lng):
            
                    json_record = dumps({
                        'lat': lat,
                        'lng': lng,
                        'timestamp': time()
                    }, sort_keys = True)
                    
                    self.json_geo_file.write(json_record + '\n')
                
                self.last_time_geolocation_was_checked = time()
        
        if log_type in TYPES_FOR_RAW_PACKET_LOGGING:
    
            json_record = dumps({
                'log_type': log_type,
                'log_frame': b64encode(log_header + log_payload).decode('ascii'),
                'timestamp': time()
            }, sort_keys = True)
            
            self.json_geo_file.write(json_record + '\n')
    
    def __del__(self):
        
        self.json_geo_file.close()

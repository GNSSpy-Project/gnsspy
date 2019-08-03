"""
Constant values used in the package are defined here.
"""

_CLIGHT = LIGHT_SPEED = 299792458.0 # speed of light [unit: m/s]
_OMEGA = 7.2921151467e-05 # angular rotation of Earth [unit:rad/s]

_SYSTEM_NAME = {'G' : 'GPS',
                'R' : 'GLONASS',
                'E' : 'GALILEO',
                'C' : 'COMBASS',
                'J' : 'QZSS',
                'I' : 'IRNSS',
                'S' : 'SBAS'}


_SYSTEM_RNX3  = {'GPS': {
                         "L1": {"Pseudorange"  : {"C1C","C1S","C1L","C1X","C1P","C1W","C1Y","C1M"},
                                "Carrierphase" : {"L1C","L1S","L1L","L1X","L1P","L1W","L1Y","L1M","L1N"},
                                "Doppler"      : {"D1C","D1S","D1L","D1X","D1P","D1W","D1Y","D1M","D1N"},
                                "Signal"       : {"S1C","S1S","S1L","S1X","S1P","S1W","S1Y","S1M","S1N"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2C","C2D","C2S","C2L","C2X","C2P","C2W","C2Y","C2M"},
                                "Carrierphase" : {"L2C","L2D","L2S","L2L","L2X","L2P","L2W","L2Y","L2M","L2N"},
                                "Doppler"      : {"D2C","D2D","D2S","D2L","D2X","D2P","D2W","D2Y","D2M","D2N"},
                                "Signal"       : {"S2C","S2D","S2S","S2L","S2X","S2P","S2W","S2Y","S2M","S2N"},
                                "Frequency"    : 1227600000},# END OF L2
                         "L5": {"Pseudorange"  : {"C5I","C5Q","C5X"},
                                "Carrierphase" : {"L5I","L5Q","L5X"},
                                "Doppler"      : {"D5I","D5Q","D5X"},
                                "Signal"       : {"S5I","S5Q","S5X"},
                                "Frequency"    : 1176450000} # END OF L5
                        }, # END OF GPS
            'GLONASS' : {
                         "L1": {"Pseudorange"  : {"C1C","C1P"},
                                "Carrierphase" : {"L1C","L1P"},
                                "Doppler"      : {"D1C","D1P"},
                                "Signal"       : {"S1C","S1P"},
                                "Frequency"    : 1602000000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2C","C2P"},
                                "Carrierphase" : {"L2C","L2P"},
                                "Doppler"      : {"D2C","D2P"},
                                "Signal"       : {"S2C","S2P"},
                                "Frequency"    : 1246000000}, # END OF L2
                         "L3": {"Pseudorange"  : {"C3I","C3Q","C3X"},
                                "Carrierphase" : {"L3I","L3Q","L3X"},
                                "Doppler"      : {"D3I","D3Q","D3X"},
                                "Signal"       : {"S3I","S3Q","S3X"},
                                "Frequency"    : 1202025000}, # END OF L3
                         "L4": {"Pseudorange"  : {"C4A","C4B","C4X"},
                                "Carrierphase" : {"L4A","L4B","L4X"},
                                "Doppler"      : {"D4A","D4B","D4X"},
                                "Signal"       : {"S4A","S4B","S4X"},
                                "Frequency"    : 1600995000}, # END OF L4
                         "L6": {"Pseudorange"  : {"C6A","C6B","C6X"},
                                "Carrierphase" : {"L6A","L6B","L6X"},
                                "Doppler"      : {"D6A","D6B","D6X"},
                                "Signal"       : {"S6A","S6B","S6X"},
                                "Frequency"    : 1248060000} # END OF L6
                        }, # END OF GLONASS
            'GALILEO' : {
                         "L1": {"Pseudorange"  : {"C1A","C1B","C1C","C1X","C1Z"},
                                "Carrierphase" : {"L1A","L1B","L1C","L1X","L1Z"},
                                "Doppler"      : {"D1A","D1B","D1C","D1X","D1Z"},
                                "Signal"       : {"S1A","S1B","S1C","S1X","S1Z"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L5": {"Pseudorange"  : {"C5I","C5Q","C5X"},
                                "Carrierphase" : {"L5I","L5Q","L5X"},
                                "Doppler"      : {"D5I","D5Q","D5X"},
                                "Signal"       : {"S5I","S5Q","S5X"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6A","C6B","C6C","C6X","C6Z"},
                                "Carrierphase" : {"L6A","L6B","L6C","L6X","L6Z"},
                                "Doppler"      : {"D6A","D6B","D6C","D6X","D6Z"},
                                "Signal"       : {"S6A","S6B","S6C","S6X","S6Z"},
                                "Frequency"    : 1278750000}, # END OF L6
                         "L7": {"Pseudorange"  : {"C7I","C7Q","C7X"},
                                "Carrierphase" : {"L7I","L7Q","L7X"},
                                "Doppler"      : {"D7I","D7Q","D7X"},
                                "Signal"       : {"S7I","S7Q","S7X"},
                                "Frequency"    : 1207140000}, # END OF L7
                         "L8": {"Pseudorange"  : {"C8I","C8Q","C8X"},
                                "Carrierphase" : {"L8I","L8Q","L8X"},
                                "Doppler"      : {"D8I","D8Q","D8X"},
                                "Signal"       : {"S8I","S8Q","S8X"},
                                "Frequency"    : 1191795000}, # END OF L8
                        }, # END OF GALILEO
            'COMPASS' : {
                         "L1": {"Pseudorange"  : {"C1D","C1P","C1X","C1A"},
                                 "Carrierphase": {"L1D","L1P","L1X","L1A"},
                                 "Doppler"     : {"D1D","D1P","D1X","D1A"},
                                 "Signal"      : {"S1D","S1P","S1X","S1A"},
                                 "Frequency"   : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2I","C2Q","C2X"},
                                "Carrierphase" : {"L2I","L2Q","L2X"},
                                "Doppler"      : {"D2I","D2Q","D2X"},
                                "Signal"       : {"S2I","S2Q","S2X"},
                                "Frequency"    : 1561098000}, # END OF L2
                         "L5": {"Pseudorange"  : {"C5D","C5P","C5X"},
                                "Carrierphase" : {"L5D","L5P","L5X"},
                                "Doppler"      : {"D5D","D5P","D5X"},
                                "Signal"       : {"S5D","S5P","S5X"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6I","C6Q","C6X","C6A"},
                                "Carrierphase" : {"L6I","L6Q","L6X","L6A"},
                                "Doppler"      : {"D6I","D6Q","D6X","D6A"},
                                "Signal"       : {"S6I","S6Q","S6X","S6A"},
                                "Frequency"    : 1268520000}, # END OF L6
                         "L7": {"Pseudorange"  : {"C7I","C7Q","C7X","C7D","C7P","C7Z"},
                                "Carrierphase" : {"L7I","L7Q","L7X","L7D","L7P","L7Z"},
                                "Doppler"      : {"D7I","D7Q","D7X","D7D","D7P","D7Z"},
                                "Signal"       : {"S7I","S7Q","S7X","S7D","S7P","S7Z"},
                                "Frequency"    : 1207140000}, # END OF L7
                         "L8": {"Pseudorange"  : {"C8D","C8P","C8X"},
                                "Carrierphase" : {"L8D","L8P","L8X"},
                                "Doppler"      : {"D8D","D8P","D8X"},
                                "Signal"       : {"S8D","S8P","S8X"},
                                "Frequency"    : 1191795000} # END OF L8
                        }, # END OF COMPASS
            'QZSS'    : {
                         "L1": {"Pseudorange"  : {"C1C","C1S","C1L","C1X","C1Z"},
                                 "Carrierphase": {"L1C","L1S","L1L","L1X","L1Z"},
                                 "Doppler"     : {"D1C","D1S","D1L","D1X","D1Z"},
                                 "Signal"      : {"S1C","S1S","S1L","S1X","S1Z"},
                                 "Frequency"   : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2S","C2L","C2X"},
                                 "Carrierphase": {"L2S","L2L","L2X"},
                                 "Doppler"     : {"D2S","D2L","D2X"},
                                 "Signal"      : {"S2S","S2L","S2X"},
                                 "Frequency"   : 1227600000}, # END OF L2
                         "L5": {"Pseudorange"  : {"C5I","C5Q","C5X","C5D","C5P","C5Z"},
                                 "Carrierphase": {"L5I","L5Q","L5X","L5D","L5P","L5Z"},
                                 "Doppler"     : {"D5I","D5Q","D5X","D5D","D5P","D5Z"},
                                 "Signal"      : {"S5I","S5Q","S5X","S5D","S5P","S5Z"},
                                 "Frequency"   : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6S","C6L","C6X","C6E","C6Z"},
                                 "Carrierphase": {"L6S","L6L","L6X","L6E","L6Z"},
                                 "Doppler"     : {"D6S","D6L","D6X","D6E","D6Z"},
                                 "Signal"      : {"S6S","S6L","S6X","S6E","S6Z"},
                                 "Frequency"   : 1278750000} # END OF L6
                        }, # END OF QZSS
            'IRNSS'   : {
                         "L5": {"Pseudorange"  : {"C5A","C5B","C5C","C5X"},
                                "Carrierphase" : {"L5A","L5B","L5C","L5X"},
                                "Doppler"      : {"D5A","D5B","D5C","D5X"},
                                "Signal"       : {"S5A","S5B","S5C","S5X"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L9": {"Pseudorange"  : {"C9A","C9B","C9C","C9X"},
                                "Carrierphase" : {"L9A","L9B","L9C","L9X"},
                                "Doppler"      : {"D9A","D9B","D9C","D9X"},
                                "Signal"       : {"S9A","S9B","S9C","S9X"},
                                "Frequency"    : 2492028000}, # END OF L9
                        }, # END OF IRNSS
            'SBAS'    : {
                         "L1": {"Pseudorange"  : {"C1C"},
                                "Carrierphase" : {"L1C"},
                                "Doppler"      : {"D1C"},
                                "Signal"       : {"S1C"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L5": {"Pseudorange"  : {"C5I","C5Q","C5X"},
                                "Carrierphase" : {"C5I","C5Q","C5X"},
                                "Doppler"      : {"C5I","C5Q","C5X"},
                                "Signal"       : {"C5I","C5Q","C5X"},
                                "Frequency"    : 1176450000} # END OF L5
                        }, # END OF SBAS
            }

_SYSTEM_RNX2  = {'GPS' : {
                         "L1": {"Pseudorange"  : {"C1","P1"},
                                "Carrierphase" : {"L1"},
                                "Doppler"      : {"D1"},
                                "Signal"       : {"S1"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2","P2"},
                                "Carrierphase" : {"L2"},
                                "Doppler"      : {"D2"},
                                "Signal"       : {"S2"},
                                "Frequency"    : 1227600000},# END OF L2
                         "L5": {"Pseudorange"  : {"C5"},
                                "Carrierphase" : {"L5"},
                                "Doppler"      : {"D5"},
                                "Signal"       : {"S5"},
                                "Frequency"    : 1176450000} # END OF L5
                        }, # END OF GPS
            'GLONASS' : {
                         "L1": {"Pseudorange"  : {"C1","P1"},
                                "Carrierphase" : {"L1"},
                                "Doppler"      : {"D1"},
                                "Signal"       : {"S1"},
                                "Frequency"    : 1602000000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2","P2"},
                                "Carrierphase" : {"L2"},
                                "Doppler"      : {"D2"},
                                "Signal"       : {"S2"},
                                "Frequency"    : 1246000000}, # END OF L2
                         "L3": {"Pseudorange"  : {"C3"},
                                "Carrierphase" : {"L3"},
                                "Doppler"      : {"D3"},
                                "Signal"       : {"S3"},
                                "Frequency"    : 1202025000}, # END OF L3
                         "L4": {"Pseudorange"  : {"C4"},
                                "Carrierphase" : {"L4"},
                                "Doppler"      : {"D4"},
                                "Signal"       : {"S4"},
                                "Frequency"    : 1600995000}, # END OF L4
                         "L6": {"Pseudorange"  : {"C6"},
                                "Carrierphase" : {"L6"},
                                "Doppler"      : {"D6"},
                                "Signal"       : {"S6"},
                                "Frequency"    : 1248060000} # END OF L6
                        }, # END OF GLONASS
            'GALILEO' : {
                         "L1": {"Pseudorange"  : {"C1"},
                                "Carrierphase" : {"L1"},
                                "Doppler"      : {"D1"},
                                "Signal"       : {"S1"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L5": {"Pseudorange"  : {"C5"},
                                "Carrierphase" : {"L5"},
                                "Doppler"      : {"D5"},
                                "Signal"       : {"S5"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6"},
                                "Carrierphase" : {"L6"},
                                "Doppler"      : {"D6"},
                                "Signal"       : {"S6"},
                                "Frequency"    : 1278750000}, # END OF L6
                         "L7": {"Pseudorange"  : {"C7"},
                                "Carrierphase" : {"L7"},
                                "Doppler"      : {"D7"},
                                "Signal"       : {"S7"},
                                "Frequency"    : 1207140000}, # END OF L7
                         "L8": {"Pseudorange"  : {"C8"},
                                "Carrierphase" : {"L8"},
                                "Doppler"      : {"D8"},
                                "Signal"       : {"S8"},
                                "Frequency"    : 1191795000}, # END OF L8
                        }, # END OF GALILEO
            'COMPASS' : {
                         "L1": {"Pseudorange"  : {"C1"},
                                 "Carrierphase": {"L1"},
                                 "Doppler"     : {"D1"},
                                 "Signal"      : {"S1"},
                                 "Frequency"   : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2"},
                                "Carrierphase" : {"L2"},
                                "Doppler"      : {"D2"},
                                "Signal"       : {"S2"},
                                "Frequency"    : 1561098000}, # END OF L2
                         "L5": {"Pseudorange"  : {"C5"},
                                "Carrierphase" : {"L5"},
                                "Doppler"      : {"D5"},
                                "Signal"       : {"S5"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6"},
                                "Carrierphase" : {"L6"},
                                "Doppler"      : {"D6"},
                                "Signal"       : {"S6"},
                                "Frequency"    : 1268520000}, # END OF L6
                         "L7": {"Pseudorange"  : {"C7"},
                                "Carrierphase" : {"L7"},
                                "Doppler"      : {"D7"},
                                "Signal"       : {"S7"},
                                "Frequency"    : 1207140000}, # END OF L7
                         "L8": {"Pseudorange"  : {"C8"},
                                "Carrierphase" : {"L8"},
                                "Doppler"      : {"D8"},
                                "Signal"       : {"S8"},
                                "Frequency"    : 1191795000} # END OF L8
                        }, # END OF COMPASS
            'QZSS'    : {
                         "L1": {"Pseudorange"  : {"C1"},
                                 "Carrierphase": {"L1"},
                                 "Doppler"     : {"D1"},
                                 "Signal"      : {"S1"},
                                 "Frequency"   : 1575420000}, # END OF L1
                         "L2": {"Pseudorange"  : {"C2"},
                                 "Carrierphase": {"L2"},
                                 "Doppler"     : {"D2"},
                                 "Signal"      : {"S2"},
                                 "Frequency"   : 1227600000}, # END OF L2
                         "L5": {"Pseudorange"  : {"C5"},
                                 "Carrierphase": {"L5"},
                                 "Doppler"     : {"D5"},
                                 "Signal"      : {"S5"},
                                 "Frequency"   : 1176450000}, # END OF L5
                         "L6": {"Pseudorange"  : {"C6"},
                                 "Carrierphase": {"L6"},
                                 "Doppler"     : {"D6"},
                                 "Signal"      : {"S6"},
                                 "Frequency"   : 1278750000} # END OF L6
                        }, # END OF QZSS
            'IRNSS'   : {
                         "L5": {"Pseudorange"  : {"C5"},
                                "Carrierphase" : {"L5"},
                                "Doppler"      : {"D5"},
                                "Signal"       : {"S5"},
                                "Frequency"    : 1176450000}, # END OF L5
                         "L9": {"Pseudorange"  : {"C9"},
                                "Carrierphase" : {"L9"},
                                "Doppler"      : {"D9"},
                                "Signal"       : {"S9"},
                                "Frequency"    : 2492028000}, # END OF L9
                        }, # END OF IRNSS
            'SBAS'    : {
                         "L1": {"Pseudorange"  : {"C1"},
                                "Carrierphase" : {"L1"},
                                "Doppler"      : {"D1"},
                                "Signal"       : {"S1"},
                                "Frequency"    : 1575420000}, # END OF L1
                         "L5": {"Pseudorange"  : {"C5"},
                                "Carrierphase" : {"C5"},
                                "Doppler"      : {"C5"},
                                "Signal"       : {"C5"},
                                "Frequency"    : 1176450000} # END OF L5
                        }, # END OF SBAS
            }

def _system_name(satellite_list):
    system = ["GPS"     if sv[0]=="G" else 
              "GLONASS" if sv[0]=="R" else 
              "COMPASS" if sv[0]=="C" else 
              "GALILEO" if sv[0]=="E" else
              "QZSS"    if sv[0]=="J" else
              "IRNSS"   if sv[0]=="I" else 
              "SBAS"    if sv[0]=="S" else 
              "UNKNOWN" for sv in satellite_list]
    return system

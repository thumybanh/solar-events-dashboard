import math
import noaa_matcher
import json

CDELT = 0.600000023842
HPCCENTER = 4096.0 / 2.0

rsun_meters = 696000000.0
dsun_meters = 149597870691.0


def convert_hgs_to_pix(x,y):
    hcc_x, hcc_y = convertHG_HCC(x, y)
    hpc_x, hpc_y = convertHCC_HPC(hcc_x, hcc_y)
    
    pix_x = HPCCENTER + (hpc_x/CDELT)
    pix_y = HPCCENTER - (hpc_y/CDELT)
    
    return pix_x/8.0, pix_y/8.0

def convertHG_HCC(hglon_deg, hglat_deg):
    b0_deg = 0
    l0_deg = 0
    lon = math.radians(hglon_deg)
    lat = math.radians(hglat_deg)
    
    cosb = math.cos(math.radians(b0_deg))
    sinb = math.sin(math.radians(b0_deg))
    
    lon = lon - math.radians(l0_deg)
    
    cosx = math.cos(lon)
    sinx = math.sin(lon)
    cosy = math.cos(lat)
    siny = math.sin(lat)

    #Perform the conversion.
    x = rsun_meters * cosy * sinx
    y = rsun_meters * (siny * cosb - cosy * cosx * sinb)
    
    return x, y
    

def convertHCC_HPC(x, y):
#     print("HCC: ",  x, y)
#     print(math.pow(rsun_meters, 2) - math.pow(x, 2) - math.pow(y, 2))
    try:
        z = math.sqrt(math.pow(rsun_meters, 2) - math.pow(x, 2) - math.pow(y, 2))
    except ValueError:
        z=0

    zeta = dsun_meters - z
    distance = math.sqrt(math.pow(x, 2) + math.pow(y, 2) + math.pow(zeta, 2))
    hpcx = math.degrees(math.atan2(x, zeta))
    hpcy = math.degrees(math.asin(y / distance))

    #if angle_units == 'arcsec' :
    hpcx = 60 * 60 * hpcx
    hpcy = 60 * 60 * hpcy

    return hpcx, hpcy



with open('events.json', 'r') as f: 
    events = json.load(f)

    for event in events: 
        lat, lon = noaa_matcher.convert_position(event['event_position'])
        pix_x, pix_y = convert_hgs_to_pix(lon, lat)
        event['pix_x'] = pix_x
        event['pix_y'] = pix_y
    
with open('events.json', 'w') as w: 
    json.dump(events, w, indent = 2)

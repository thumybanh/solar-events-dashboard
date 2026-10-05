import json
import math
import os

import noaa_matcher

EVENTS_PATH = noaa_matcher.EVENTS_PATH

CDELT = 0.600000023842
HPCCENTER = 4096.0 / 2.0

rsun_meters = 696000000.0
dsun_meters = 149597870691.0


def convert_hgs_to_pix(x,y):
    hcc_x, hcc_y = convertHG_HCC(x, y)
    hpc_x, hpc_y = convertHCC_HPC(hcc_x, hcc_y)
    
    pix_x = HPCCENTER + (hpc_x/CDELT)
    pix_y = HPCCENTER - (hpc_y/CDELT) # flip the minus sign due to the screen coordinate is behaving opposite
    
    return pix_x/8.0, pix_y/8.0 # pandey's original 4096 x 4096 px image -> resize it to 512 x 512

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


def location_to_pix(text):
    """'N09W89' or LMSAL's 'N09W89( 4534 )' -> (pix_x, pix_y) on the 512 px image, or (None, None)."""
    try:
        lat, lon = noaa_matcher.convert_position((text or '').strip())
    except (IndexError, ValueError):
        # blank or unreadable position (LMSAL leaves some blank; most NOAA flares have none)
        return None, None
    return convert_hgs_to_pix(lon, lat)


def add_pixels(path, key):
    """Writes pix_x/pix_y into every row of a JSON file from its `key` position. Returns how many had none."""
    with open(path) as f:
        rows = json.load(f)
    missing = 0
    for row in rows:
        row['pix_x'], row['pix_y'] = location_to_pix(row.get(key))
        missing += row['pix_x'] is None
    with open(path + '.tmp', 'w') as f:
        json.dump(rows, f, indent=2)
    os.replace(path + '.tmp', path)
    return missing


if __name__ == '__main__':
    from noaa_events import NOAA_EVENTS_PATH
    from sciquality_events import SCIQUALITY_EVENTS_PATH

    for path, key in ((EVENTS_PATH, 'event_position'), (NOAA_EVENTS_PATH, 'location'),
                      (SCIQUALITY_EVENTS_PATH, 'location')):
        if os.path.exists(path):
            missing = add_pixels(path, key)
            print(f"{os.path.basename(path)}: {missing} without a position")

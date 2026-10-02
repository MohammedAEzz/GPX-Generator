#!/usr/bin/env python3
"""Real road GPX generator (Python 3, curl; no pip dependencies).
Run interactively: python3 generate_real_naveera_gpx.py
Or: python3 generate_real_naveera_gpx.py --input trip.json --output gpx

Normal JSON:
{"type":"normal","name":"Passenger A","start":[39.69,-105.08],
 "pickup":[39.698010,-105.070418],"dropoff":[39.710486,-105.064513]}
Pooled JSON (steps MUST be in the intended navigation order):
{"type":"pooled","name":"Pool A","start":[39.69,-105.08],"steps":[
 {"kind":"pickup","name":"Passenger A","point":[39.698010,-105.070418]},
 {"kind":"pickup","name":"Passenger B","point":[39.698010,-105.070418]},
 {"kind":"dropoff","name":"Passenger A","point":[39.710486,-105.064513]},
 {"kind":"dropoff","name":"Passenger B","point":[39.72,-105.06]}]}
Optional JSON fields: speed_mph (default 20), pause_seconds (default 0).
Only consecutive identical coordinates are merged; later visits are preserved.
GPX uses timestamped wpt points for simulator playback, matching the original.
Road routing needs internet access to the OSRM endpoint. Names are XML escaped.
"""
import argparse
import json
import math
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

OSRM_BASE = 'https://router.project-osrm.org/route/v1/driving'
NS = 'http://www.topografix.com/GPX/1/1'
ET.register_namespace('', NS)

def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Each point must be [latitude, longitude].')
    if any(isinstance(x, bool) for x in value):
        raise ValueError('Coordinates must be numbers.')
    lat, lon = map(float, value)
    if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError('Invalid latitude/longitude range.')
    return lat, lon

def positive(value, label, zero=False):
    n = float(value)
    if not math.isfinite(n) or (n < 0 if zero else n <= 0):
        raise ValueError(label + (' must be >= 0.' if zero else ' must be > 0.'))
    return n

def stops(config):
    start = point(config['start'])
    name = str(config['name']).strip()
    if not name:
        raise ValueError('Trip name is required.')
    if config['type'] == 'normal':
        raw = [{'kind': 'pickup', 'name': name, 'point': config['pickup']},
               {'kind': 'dropoff', 'name': name, 'point': config['dropoff']}]
    elif config['type'] == 'pooled':
        raw = config['steps']
        if not isinstance(raw, list) or not raw:
            raise ValueError('Pooled trips need an ordered, nonempty steps list.')
    else:
        raise ValueError('Trip type must be normal or pooled.')
    merged = []
    for step in raw:
        if step['kind'] not in ('pickup', 'dropoff'):
            raise ValueError('Step kind must be pickup or dropoff.')
        p = point(step['point'])
        label = f"{step['kind']}: {step['name']}"
        if merged and merged[-1]['point'] == p:
            merged[-1]['labels'].append(label)
        else:
            merged.append({'point': p, 'labels': [label]})
    return name, start, merged

def request_route(start, end, base):
    coords = f'{start[1]:.7f},{start[0]:.7f};{end[1]:.7f},{end[0]:.7f}'
    url = base.rstrip('/') + '/' + coords + '?' + urlencode({'overview':'full','geometries':'geojson','steps':'false'})
    proc = subprocess.run(['curl','--fail','--silent','--show-error','--location',
                           '--retry','2','--connect-timeout','15','--max-time','45',url],
                          capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or 'Routing request failed.')
    data = json.loads(proc.stdout)
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise RuntimeError('OSRM did not return a route: ' + str(data.get('code')))
    route = data['routes'][0]
    points = [point([lat, lon]) for lon, lat in route['geometry']['coordinates']]
    if len(points) < 2:
        raise RuntimeError('OSRM returned insufficient route geometry.')
    distance = positive(route['distance'], 'Route distance', zero=True)
    return distance, points

def distance_miles(a, b):
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 7917.5226 * math.asin(math.sqrt(min(1, max(0, h))))

def write_gpx(path, name, points, when, speed):
    root = ET.Element(f'{{{NS}}}gpx', version='1.1', creator='Naveera GPX Test Generator')
    metadata = ET.SubElement(root, f'{{{NS}}}metadata')
    ET.SubElement(metadata, f'{{{NS}}}name').text = name
    for i, p in enumerate(points):
        if i:
            when += timedelta(seconds=max(1, distance_miles(points[i-1], p)/speed*3600))
        wpt = ET.SubElement(root, f'{{{NS}}}wpt', lat=f'{p[0]:.7f}', lon=f'{p[1]:.7f}')
        ET.SubElement(wpt, f'{{{NS}}}name').text = f'Route Point {i+1}'
        ET.SubElement(wpt, f'{{{NS}}}time').text = when.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)
    return when

def ask_point(label):
    while True:
        try:
            return point(input(label + ' (latitude, longitude): ').split(','))
        except ValueError as error:
            print(error)

def interactive():
    kind = input('Trip type (1 = normal, 2 = pooled): ').strip()
    if kind not in ('1','2','normal','pooled'):
        raise ValueError('Select 1 or 2.')
    config = {'type':'normal' if kind in ('1','normal') else 'pooled',
              'name':input('Passenger / trip / pool name: ').strip(),
              'start':ask_point('Current location / start')}
    if config['type'] == 'normal':
        config['pickup'] = ask_point('Pickup')
        config['dropoff'] = ask_point('Dropoff')
    else:
        count = int(input('Number of ordered steps (including shared passenger steps): '))
        config['steps'] = []
        for i in range(count):
            print(f'Step {i+1}')
            config['steps'].append({'kind':input('Kind (pickup/dropoff): ').strip().lower(),
                                    'name':input('Passenger(s) / stop name: ').strip(),
                                    'point':ask_point('Stop')})
    config['speed_mph'] = input('Speed mph [20]: ').strip() or 20
    config['pause_seconds'] = input('Pause at each stop in seconds [0]: ').strip() or 0
    return config

def generate(config, output, base=OSRM_BASE):
    name, current, ordered = stops(config)
    speed = positive(config.get('speed_mph',20), 'Speed')
    pause = positive(config.get('pause_seconds',0), 'Pause', zero=True)
    when = datetime.now(timezone.utc)
    slug = re.sub(r'[^\w-]+','_',name, flags=re.UNICODE).strip('_')[:80] or 'trip'
    folder = Path(output)/slug
    folder.mkdir(parents=True, exist_ok=True)
    # Refuse to overwrite a previous test run.
    if any(folder.iterdir()):
        raise ValueError(f'Output folder is not empty: {folder}. Choose another --output or trip name.')
    plan = []
    for index, stop in enumerate(ordered, 1):
        label = ' + '.join(stop['labels'])
        if current == stop['point']:
            plan.append({'step':index,'labels':stop['labels'],'point':stop['point'],
                         'file':None,'note':'Already at this stop; no driving leg.'})
            when += timedelta(seconds=pause)
            continue
        meters, geometry = request_route(current, stop['point'], base)
        path = folder/f'{index:02d}_to_stop_{index}.gpx'
        when = write_gpx(path, f'{name}: {label}', geometry, when, speed)
        plan.append({'step':index,'labels':stop['labels'],'point':stop['point'],
                     'file':path.name,'distance_miles':meters/1609.344,
                     'snapped_start':geometry[0],'snapped_end':geometry[-1]})
        print(f'{path.name}: {label} ({meters/1609.344:.2f} mi)')
        when += timedelta(seconds=pause)
        current = stop['point']
    (folder/'manifest.json').write_text(json.dumps({'name':name,'type':config['type'],
        'start':point(config['start']),'stops':plan},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Created: {folder.resolve()}')
    return plan

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, help='JSON trip configuration; omitted = interactive prompts')
    parser.add_argument('--output', default='gpx_output', help='Output parent directory')
    parser.add_argument('--osrm-base', default=OSRM_BASE, help='OSRM driving route endpoint')
    args = parser.parse_args()
    try:
        config = json.loads(args.input.read_text(encoding='utf-8')) if args.input else interactive()
        generate(config, args.output, args.osrm_base)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())

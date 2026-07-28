"""
GPX / GeoJSON 导出模块

作者: MP5录播器
"""

import json
from typing import List
from mp5_box import GPSEntry, POI
from datetime import datetime, timedelta


def export_gpx(gps_entries: List[GPSEntry], pois: List[POI] = None) -> str:
    """导出 GPX 格式 XML"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<gpx version="1.1" creator="MP5录播器" xmlns="http://www.topografix.com/GPX/1/1">')
    lines.append('  <metadata>')
    lines.append('    <name>MP5 GPS Track</name>')
    lines.append(f'    <time>{datetime.now().isoformat()}</time>')
    lines.append('  </metadata>')

    # POI waypoints
    if pois:
        for poi in pois:
            lines.append(f'  <wpt lat="{poi.latitude:.7f}" lon="{poi.longitude:.7f}">')
            lines.append(f'    <name>{poi.label}</name>')
            lines.append(f'    <time>{(datetime(2000,1,1) + timedelta(milliseconds=poi.timestamp)).isoformat()}</time>')
            lines.append('  </wpt>')

    # Track
    lines.append('  <trk>')
    lines.append('    <name>MP5 Track</name>')
    lines.append('    <trkseg>')

    for e in gps_entries:
        time_str = (datetime(2000, 1, 1) + timedelta(milliseconds=e.timestamp)).isoformat()
        lines.append(f'      <trkpt lat="{e.latitude:.7f}" lon="{e.longitude:.7f}">')
        lines.append(f'        <ele>{e.altitude:.1f}</ele>')
        lines.append(f'        <time>{time_str}</time>')
        if e.speed > 0:
            lines.append(f'        <extensions><speed>{e.speed / 3.6:.2f}</speed></extensions>')
        lines.append('      </trkpt>')

    lines.append('    </trkseg>')
    lines.append('  </trk>')
    lines.append('</gpx>')

    return '\n'.join(lines)


def export_geojson(gps_entries: List[GPSEntry], pois: List[POI] = None) -> str:
    """导出 GeoJSON 格式"""
    features = []

    # 轨迹 LineString
    coordinates = [[e.longitude, e.latitude, e.altitude] for e in gps_entries]
    features.append({
        'type': 'Feature',
        'properties': {
            'name': 'MP5 Track',
            'creator': 'MP5录播器',
            'pointCount': len(gps_entries),
        },
        'geometry': {
            'type': 'LineString',
            'coordinates': coordinates,
        }
    })

    # POI 标记
    if pois:
        for poi in pois:
            features.append({
                'type': 'Feature',
                'properties': {
                    'name': poi.label,
                    'type': poi.type,
                    'timestamp': poi.timestamp,
                },
                'geometry': {
                    'type': 'Point',
                    'coordinates': [poi.longitude, poi.latitude],
                }
            })

    return json.dumps({
        'type': 'FeatureCollection',
        'features': features,
    }, indent=2, ensure_ascii=False)


def export_kml(gps_entries: List[GPSEntry], pois: List[POI] = None) -> str:
    """导出 KML 格式 (Google Earth)"""
    lines = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append('<kml xmlns="http://www.opengis.net/kml/2.2">')
    lines.append('  <Document>')
    lines.append('    <name>MP5 Track</name>')
    lines.append('    <Style id="trackStyle">')
    lines.append('      <LineStyle><color>ff0066ff</color><width>3</width></LineStyle>')
    lines.append('    </Style>')

    # POI 标记
    if pois:
        for poi in pois:
            lines.append('    <Placemark>')
            lines.append(f'      <name>{poi.label}</name>')
            lines.append('      <Point>')
            lines.append(f'        <coordinates>{poi.longitude},{poi.latitude},0</coordinates>')
            lines.append('      </Point>')
            lines.append('    </Placemark>')

    # 轨迹
    lines.append('    <Placemark>')
    lines.append('      <name>MP5 Track</name>')
    lines.append('      <styleUrl>#trackStyle</styleUrl>')
    lines.append('      <LineString>')
    lines.append('        <coordinates>')
    for e in gps_entries:
        lines.append(f'          {e.longitude},{e.latitude},{e.altitude}')
    lines.append('        </coordinates>')
    lines.append('      </LineString>')
    lines.append('    </Placemark>')

    lines.append('  </Document>')
    lines.append('</kml>')

    return '\n'.join(lines)
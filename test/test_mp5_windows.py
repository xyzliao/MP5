#!/usr/bin/env python3
"""
MP5 Windows版 — 单元测试
验证 mp5_box.py 的编解码逻辑

运行: python test/test_mp5_windows.py
"""

import sys
import os
import struct
import json

# 添加 windows 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'windows'))

from mp5_box import (
    GPSEntry, SyncConfig, POI,
    parse_boxes, find_box, parse_gloc, parse_gsyn, parse_gpoi,
    write_gloc, write_gsyn, write_gpoi, write_ftyp, write_box, write_fullbox,
    mux_mp5, strip_mp5_boxes, create_sample_mp5,
    GLOC_ENTRY_SIZE
)
from mp5_parser import MP5Parser
from sync_engine import SyncEngine
from exporters import export_gpx, export_geojson, export_kml

pass_count = 0
fail_count = 0

def assert_cond(condition, message):
    global pass_count, fail_count
    if condition:
        print(f'  PASS {message}')
        pass_count += 1
    else:
        print(f'  FAIL {message}')
        fail_count += 1

def test_section(name):
    print(f'\n=== {name} ===')

# ============================================================
# 测试1: GPSEntry 编解码
# ============================================================
test_section('GPSEntry 编解码')

entry = GPSEntry(
    timestamp=1000,
    latitude=39.9042,
    longitude=116.4074,
    altitude=45.5,
    accuracy=5,
    heading=245.0,
    speed=12.3
)
encoded = entry.encode()
assert_cond(len(encoded) == GLOC_ENTRY_SIZE, f'编码大小 = {GLOC_ENTRY_SIZE} (实际: {len(encoded)})')

decoded = GPSEntry.decode(encoded)
assert_cond(decoded.timestamp == 1000, f'时间戳: {decoded.timestamp}')
assert_cond(abs(decoded.latitude - 39.9042) < 1e-6, f'纬度: {decoded.latitude}')
assert_cond(abs(decoded.longitude - 116.4074) < 1e-6, f'经度: {decoded.longitude}')
assert_cond(abs(decoded.altitude - 45.5) < 0.01, f'海拔: {decoded.altitude}')
assert_cond(decoded.accuracy == 5, f'精度: {decoded.accuracy}')
assert_cond(abs(decoded.heading - 245.0) < 0.01, f'方向: {decoded.heading}')
assert_cond(abs(decoded.speed - 12.3) < 0.01, f'速度: {decoded.speed}')

# ============================================================
# 测试2: 负数经纬度
# ============================================================
test_section('负数经纬度 (南半球/西半球)')

entry = GPSEntry(
    timestamp=0,
    latitude=-33.8688,
    longitude=-151.2093,
    altitude=-10.5,
    accuracy=3,
    heading=180.0,
    speed=0.0
)
encoded = entry.encode()
decoded = GPSEntry.decode(encoded)
assert_cond(abs(decoded.latitude - (-33.8688)) < 1e-6, f'负纬度: {decoded.latitude}')
assert_cond(abs(decoded.longitude - (-151.2093)) < 1e-6, f'负经度: {decoded.longitude}')
assert_cond(abs(decoded.altitude - (-10.5)) < 0.01, f'负海拔: {decoded.altitude}')

# ============================================================
# 测试3: SyncConfig 编解码
# ============================================================
test_section('SyncConfig 编解码')

config = SyncConfig(
    sync_mode=1,
    sync_offset=500,
    interpolation=2,
    default_view=4,
    video_ratio=0.6,
    map_style=1,
    show_trajectory=False,
    show_poi=True
)
encoded = config.encode()
decoded = SyncConfig.decode(encoded)
assert_cond(decoded.sync_mode == 1, f'sync_mode: {decoded.sync_mode}')
assert_cond(decoded.sync_offset == 500, f'sync_offset: {decoded.sync_offset}')
assert_cond(decoded.interpolation == 2, f'interpolation: {decoded.interpolation}')
assert_cond(abs(decoded.video_ratio - 0.6) < 0.001, f'video_ratio: {decoded.video_ratio}')
assert_cond(decoded.map_style == 1, f'map_style: {decoded.map_style}')
assert_cond(decoded.show_trajectory == False, f'show_trajectory: {decoded.show_trajectory}')
assert_cond(decoded.show_poi == True, f'show_poi: {decoded.show_poi}')

# ============================================================
# 测试4: gloc Box 读写
# ============================================================
test_section('gloc Box 读写')

entries = [
    GPSEntry(0, 39.9042, 116.4074, 45.5, 5, 245.0, 12.3),
    GPSEntry(1000, 39.9045, 116.4080, 46.0, 4, 250.0, 15.0),
    GPSEntry(2000, 39.9050, 116.4090, 47.0, 3, 255.0, 18.5),
]
gloc_data = write_gloc(entries)
boxes = parse_boxes(gloc_data)
assert_cond(len(boxes) == 1, f'解析出1个box (实际: {len(boxes)})')
assert_cond(boxes[0].type == 'gloc', f'box类型 = gloc')

parsed = parse_gloc(boxes[0])
assert_cond(len(parsed) == 3, f'GPS点数 = 3 (实际: {len(parsed)})')
assert_cond(abs(parsed[0].latitude - 39.9042) < 1e-6, f'首点纬度: {parsed[0].latitude}')
assert_cond(parsed[1].timestamp == 1000, f'第二点时间戳: {parsed[1].timestamp}')

# ============================================================
# 测试5: gsyn Box 读写
# ============================================================
test_section('gsyn Box 读写')

config = SyncConfig(interpolation=1, default_view=2, show_trajectory=True, show_poi=True)
gsyn_data = write_gsyn(config)
boxes = parse_boxes(gsyn_data)
assert_cond(boxes[0].type == 'gsyn', 'box类型 = gsyn')

parsed = parse_gsyn(boxes[0])
assert_cond(parsed.interpolation == 1, f'插值模式: {parsed.interpolation}')
assert_cond(parsed.show_trajectory == True, f'显示轨迹: {parsed.show_trajectory}')

# ============================================================
# 测试6: ftyp Box
# ============================================================
test_section('ftyp Box')

ftyp_data = write_ftyp('mp5v', 0, ['mp5v', 'mp41', 'isom'])
boxes = parse_boxes(ftyp_data)
assert_cond(boxes[0].type == 'ftyp', 'box类型 = ftyp')
assert_cond(boxes[0].size == 28, f'ftyp大小 = 28 (实际: {boxes[0].size})')

ftyp_payload = ftyp_data[8:]
major_brand = ftyp_payload[0:4].decode('ascii')
assert_cond(major_brand == 'mp5v', f'major_brand = mp5v (实际: {major_brand})')

# ============================================================
# 测试7: 完整 MP5 文件构建与解析
# ============================================================
test_section('完整 MP5 文件构建与解析')

mp5_data = create_sample_mp5(60)
info = MP5Parser.parse(mp5_data)

assert_cond(info.is_mp5 == True, f'是MP5文件: {info.is_mp5}')
assert_cond(info.major_brand == 'mp5v', f'major_brand = mp5v (实际: {info.major_brand})')
assert_cond('mp5v' in info.compatible_brands, '兼容品牌包含 mp5v')
assert_cond(len(info.gps_entries) == 60, f'GPS点数 = 60 (实际: {len(info.gps_entries)})')
assert_cond(len(info.pois) == 2, f'POI数 = 2 (实际: {len(info.pois)})')
assert_cond(info.sync_config is not None, '有同步规则')
assert_cond(info.sync_config.interpolation == 1, f'插值模式 = 1')

first = info.gps_entries[0]
assert_cond(39.99 < first.latitude < 40.00, f'首点纬度范围: {first.latitude}')
assert_cond(116.39 < first.longitude < 116.41, f'首点经度范围: {first.longitude}')

# ============================================================
# 测试8: 向后兼容 (strip MP5 boxes)
# ============================================================
test_section('向后兼容 (strip MP5 boxes)')

mp5_data = create_sample_mp5(30)
mp4_data = strip_mp5_boxes(mp5_data)

assert_cond(len(mp4_data) < len(mp5_data), f'MP4 < MP5 ({len(mp4_data)} < {len(mp5_data)})')

boxes = parse_boxes(mp4_data)
has_gloc = find_box(boxes, 'gloc') is not None
has_gsyn = find_box(boxes, 'gsyn') is not None
assert_cond(not has_gloc, 'strip后无gloc')
assert_cond(not has_gsyn, 'strip后无gsyn')
assert_cond(find_box(boxes, 'ftyp') is not None, 'strip后仍有ftyp')
assert_cond(find_box(boxes, 'moov') is not None, 'strip后仍有moov')
assert_cond(find_box(boxes, 'mdat') is not None, 'strip后仍有mdat')

# ============================================================
# 测试9: SyncEngine 插值
# ============================================================
test_section('SyncEngine 插值')

entries = [
    GPSEntry(0, 39.0, 116.0, 50, 5, 0, 10),
    GPSEntry(1000, 39.001, 116.001, 51, 5, 10, 12),
    GPSEntry(2000, 39.002, 116.002, 52, 5, 20, 14),
    GPSEntry(3000, 39.003, 116.003, 53, 5, 30, 16),
]
engine = SyncEngine(entries, SyncConfig(interpolation=1))

pos = engine.get_position_at_time(500)
assert_cond(pos is not None, '插值结果非空')
assert_cond(39.0 < pos.latitude < 39.001, f'插值纬度在两点之间: {pos.latitude}')

engine_nn = SyncEngine(entries, SyncConfig(interpolation=0))
pos_nn = engine_nn.get_position_at_time(500)
assert_cond(pos_nn.latitude == 39.001, f'最近邻返回第二点(t=0.5): {pos_nn.latitude}')

nearest = engine.find_nearest_by_position(39.0015, 116.0015)
assert_cond(nearest is not None, '查找最近位置非空')
assert_cond(nearest.timestamp == 2000, f'最近点时间戳 = 2000 (实际: {nearest.timestamp})')

# ============================================================
# 测试10: 速度热力图颜色
# ============================================================
test_section('速度热力图颜色')

assert_cond(SyncEngine.get_speed_color(0) == '#3b82f6', '0 km/h -> 蓝色')
assert_cond(SyncEngine.get_speed_color(10) == '#22c55e', '10 km/h -> 绿色')
assert_cond(SyncEngine.get_speed_color(40) == '#eab308', '40 km/h -> 黄色')
assert_cond(SyncEngine.get_speed_color(80) == '#f97316', '80 km/h -> 橙色')
assert_cond(SyncEngine.get_speed_color(150) == '#ef4444', '150 km/h -> 红色')

# ============================================================
# 测试11: 统计信息
# ============================================================
test_section('统计信息')

entries = [
    GPSEntry(0, 39.0, 116.0, 50, 5, 0, 10),
    GPSEntry(1000, 39.001, 116.001, 51, 5, 10, 20),
    GPSEntry(2000, 39.002, 116.002, 52, 5, 20, 30),
]
engine = SyncEngine(entries)
stats = engine.get_stats()

assert_cond(stats['point_count'] == 3, f'点数 = 3 (实际: {stats["point_count"]})')
assert_cond(stats['max_speed'] == 30, f'最高速度 = 30 (实际: {stats["max_speed"]})')
assert_cond(stats['duration'] == 2.0, f'时长 = 2.0s (实际: {stats["duration"]})')
assert_cond(stats['distance'] > 0, f'距离 > 0 ({stats["distance"]:.4f} km)')

# ============================================================
# 测试12: GPX 导出
# ============================================================
test_section('GPX 导出')

entries = [GPSEntry(0, 39.9042, 116.4074, 45.5, 5, 245, 12.3)]
gpx = export_gpx(entries)
assert_cond('<gpx' in gpx, '包含 <gpx> 标签')
assert_cond('<trkpt' in gpx, '包含 <trkpt> 标签')
assert_cond('lat="39.9042000"' in gpx, '包含纬度')
assert_cond('lon="116.4074000"' in gpx, '包含经度')

# ============================================================
# 测试13: GeoJSON 导出
# ============================================================
test_section('GeoJSON 导出')

entries = [GPSEntry(0, 39.9042, 116.4074, 45.5, 5, 245, 12.3)]
geojson = export_geojson(entries)
data = json.loads(geojson)
assert_cond(data['type'] == 'FeatureCollection', 'type = FeatureCollection')
assert_cond(data['features'][0]['geometry']['type'] == 'LineString', 'geometry = LineString')
assert_cond(len(data['features'][0]['geometry']['coordinates']) == 1, '坐标点数 = 1')

# ============================================================
# 测试14: KML 导出
# ============================================================
test_section('KML 导出')

entries = [GPSEntry(0, 39.9042, 116.4074, 45.5, 5, 245, 12.3)]
kml = export_kml(entries)
assert_cond('<kml' in kml, '包含 <kml> 标签')
assert_cond('<LineString>' in kml, '包含 <LineString> 标签')
assert_cond('116.4074,39.9042' in kml, '包含坐标')

# ============================================================
# 测试15: POI 编解码
# ============================================================
test_section('POI 编解码')

poi = POI(5000, 39.99, 116.40, '测试标记', 'poi')
encoded = poi.encode()
decoded, _ = POI.decode(encoded, 0)
assert_cond(decoded.timestamp == 5000, f'时间戳: {decoded.timestamp}')
assert_cond(abs(decoded.latitude - 39.99) < 1e-6, f'纬度: {decoded.latitude}')
assert_cond(decoded.label == '测试标记', f'标签: {decoded.label}')

# ============================================================
# 测试16: 文件大小估算
# ============================================================
test_section('文件大小估算')

size_1h = 8 + 4 + 4 + 3600 * GLOC_ENTRY_SIZE
assert_cond(size_1h < 130 * 1024, f'1Hz/1h < 130KB (实际: {size_1h/1024:.1f}KB)')

size_10h = 8 + 4 + 4 + 36000 * GLOC_ENTRY_SIZE
assert_cond(size_10h < 1300 * 1024, f'10Hz/1h < 1.3MB (实际: {size_10h/1024/1024:.2f}MB)')

# ============================================================
# 测试结果
# ============================================================
print(f'\n{"=" * 50}')
print(f'测试结果: {pass_count} 通过, {fail_count} 失败')
if fail_count == 0:
    print('全部通过!')
else:
    print('有失败的测试')
sys.exit(0 if fail_count == 0 else 1)
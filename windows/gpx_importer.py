"""
GPX 文件导入模块
解析 GPX 文件，提取轨迹点，转换为 GPSEntry 列表

作者: MP5录播器
"""

import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
from mp5_box import GPSEntry


def parse_gpx(gpx_content: str, video_duration_ms: float = None) -> List[GPSEntry]:
    """
    解析 GPX 文件内容，返回 GPSEntry 列表

    @param gpx_content: GPX XML 文本
    @param video_duration_ms: 视频时长（毫秒），用于时间映射
    @return: GPSEntry 列表
    """
    try:
        root = ET.fromstring(gpx_content)
    except ET.ParseError as e:
        raise ValueError(f'GPX解析失败: {e}')

    # GPX 命名空间
    ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}

    entries = []

    # 查找所有 trkpt（轨迹点）
    trkpts = root.findall('.//gpx:trkpt', ns)
    if not trkpts:
        # 尝试无命名空间
        trkpts = root.findall('.//trkpt')

    for pt in trkpts:
        lat_str = pt.get('lat')
        lon_str = pt.get('lon')
        if not lat_str or not lon_str:
            continue

        lat = float(lat_str)
        lon = float(lon_str)

        # 海拔
        ele_elem = pt.find('gpx:ele', ns)
        if ele_elem is None:
            ele_elem = pt.find('ele')
        altitude = float(ele_elem.text) if ele_elem is not None else 0.0

        # 时间
        time_elem = pt.find('gpx:time', ns)
        if time_elem is None:
            time_elem = pt.find('time')
        if time_elem is not None and time_elem.text:
            # 解析ISO时间，计算相对于第一个点的毫秒偏移
            from datetime import datetime
            try:
                t = datetime.fromisoformat(time_elem.text.replace('Z', '+00:00'))
                if not hasattr(parse_gpx, '_first_time'):
                    parse_gpx._first_time = t
                timestamp = int((t - parse_gpx._first_time).total_seconds() * 1000)
            except:
                timestamp = 0
        else:
            timestamp = 0

        # 速度（扩展字段）
        speed = 0.0
        speed_elem = pt.find('.//gpx:speed', ns)
        if speed_elem is None:
            speed_elem = pt.find('.//speed')
        if speed_elem is not None and speed_elem.text:
            try:
                speed = float(speed_elem.text) * 3.6  # m/s → km/h
            except:
                pass

        # 方向（扩展字段）
        heading = 0.0
        course_elem = pt.find('.//gpx:course', ns)
        if course_elem is None:
            course_elem = pt.find('.//course')
        if course_elem is not None and course_elem.text:
            try:
                heading = float(course_elem.text)
            except:
                pass

        entries.append(GPSEntry(
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            altitude=altitude,
            accuracy=5,
            heading=heading,
            speed=speed,
        ))

    # 重置静态变量
    if hasattr(parse_gpx, '_first_time'):
        del parse_gpx._first_time

    # 如果没有时间戳，按均匀分布映射到视频时长
    if entries and all(e.timestamp == 0 for e in entries) and video_duration_ms:
        for i, entry in enumerate(entries):
            entry.timestamp = int(i * video_duration_ms / len(entries))

    # 如果有时间戳但需要缩放到视频时长
    elif entries and video_duration_ms and entries[-1].timestamp > 0:
        gpx_duration = entries[-1].timestamp
        if gpx_duration > 0 and abs(gpx_duration - video_duration_ms) > video_duration_ms * 0.1:
            # 时间差异超过10%，进行缩放
            scale = video_duration_ms / gpx_duration
            for entry in entries:
                entry.timestamp = int(entry.timestamp * scale)

    # 计算缺失的速度和方向
    if len(entries) > 1:
        import math
        for i in range(len(entries)):
            if entries[i].speed == 0:
                if i > 0:
                    dt = (entries[i].timestamp - entries[i-1].timestamp) / 1000
                    if dt > 0:
                        # Haversine 距离
                        R = 6371000
                        dlat = math.radians(entries[i].latitude - entries[i-1].latitude)
                        dlon = math.radians(entries[i].longitude - entries[i-1].longitude)
                        a = math.sin(dlat/2)**2 + \
                            math.cos(math.radians(entries[i-1].latitude)) * \
                            math.cos(math.radians(entries[i].latitude)) * \
                            math.sin(dlon/2)**2
                        dist = R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                        entries[i].speed = (dist / dt) * 3.6  # km/h

            if entries[i].heading == 0 and i > 0:
                dlat = entries[i].latitude - entries[i-1].latitude
                dlon = entries[i].longitude - entries[i-1].longitude
                if abs(dlat) > 1e-8 or abs(dlon) > 1e-8:
                    entries[i].heading = (math.degrees(math.atan2(dlon, dlat)) + 360) % 360

    return entries


def parse_gpx_file(filepath: str, video_duration_ms: float = None) -> List[GPSEntry]:
    """从文件读取并解析 GPX"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return parse_gpx(content, video_duration_ms)


def get_video_duration(filepath: str) -> Optional[float]:
    """
    使用 ffprobe 获取视频时长（毫秒）
    如果 ffprobe 不可用，返回 None
    """
    import subprocess
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', filepath],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            duration = float(data.get('format', {}).get('duration', 0))
            return duration * 1000  # 转毫秒
    except:
        pass
    return None
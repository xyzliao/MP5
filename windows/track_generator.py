"""
模拟GPS轨迹生成器
根据视频时长生成模拟GPS轨迹，用于将MP4转换为MP5

作者: MP5录播器
"""

import math
from typing import List
from mp5_box import GPSEntry


def generate_simulated_track(
    duration_ms: float,
    start_lat: float = 39.9042,
    start_lon: float = 116.4074,
    avg_speed: float = 30.0,
    route_type: str = 'linear',
    sample_rate: int = 1
) -> List[GPSEntry]:
    """
    生成模拟GPS轨迹

    @param duration_ms: 视频时长（毫秒）
    @param start_lat: 起点纬度
    @param start_lon: 起点经度
    @param avg_speed: 平均速度（km/h）
    @param route_type: 路线类型 'linear'(直线) / 'loop'(环形) / 'winding'(蜿蜒)
    @param sample_rate: 采样率（Hz），1表示每秒一个点
    @return: GPSEntry 列表
    """
    entries = []
    duration_s = duration_ms / 1000
    interval = 1000 / sample_rate  # 毫秒
    total_points = int(duration_s * sample_rate)

    speed_mps = avg_speed / 3.6  # km/h → m/s

    for i in range(total_points + 1):
        t_ms = int(i * interval)
        t = t_ms / 1000
        progress = t / duration_s if duration_s > 0 else 0

        # 距离（米）
        distance_m = speed_mps * t

        if route_type == 'linear':
            # 直线行驶
            dlat = distance_m * 0.000009  # 纬度偏移（约1度≈111km）
            dlon = distance_m * 0.0000117
            lat = start_lat + dlat
            lon = start_lon + dlon
            heading = 45.0

        elif route_type == 'loop':
            # 环形路线
            radius_m = max(100, speed_mps * duration_s / (2 * math.pi))
            radius_deg = radius_m / 111000
            angle = progress * 2 * math.pi
            lat = start_lat + radius_deg * math.sin(angle)
            lon = start_lon + radius_deg * math.cos(angle)
            heading = (math.degrees(angle) + 90) % 360

        elif route_type == 'winding':
            # 蜿蜒路线
            base_lat = start_lat + (distance_m / 111000)
            base_lon = start_lon + (distance_m / 111000) * 0.7
            lat = base_lat + 0.0005 * math.sin(t * 0.5)
            lon = base_lon + 0.0005 * math.cos(t * 0.3)
            heading = (math.degrees(math.atan2(
                0.0005 * 0.3 * math.cos(t * 0.3),
                1 / 111000
            )) + 360) % 360

        else:
            lat = start_lat
            lon = start_lon
            heading = 0

        # 速度波动
        speed = avg_speed + avg_speed * 0.2 * math.sin(t * 0.3)
        speed = max(0, speed)

        # 海拔
        altitude = 50 + 10 * math.sin(t * 0.1)

        entries.append(GPSEntry(
            timestamp=t_ms,
            latitude=lat,
            longitude=lon,
            altitude=altitude,
            accuracy=5,
            heading=heading,
            speed=speed,
        ))

    return entries
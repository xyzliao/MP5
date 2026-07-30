"""
Sync Engine — 视频↔地图双向同步引擎

职责:
1. 时间→位置：视频播放进度变化时，计算当前 GPS 坐标并更新地图
2. 位置→时间：用户点击地图时，查找最近 GPS 采样点并跳转视频
3. 插值：支持最近邻、线性、三次样条三种插值模式

作者: 大米斗（Aniseedaliao）
"""

import math
from typing import List, Optional, Tuple
from mp5_box import GPSEntry, SyncConfig


class SyncEngine:
    """视频↔地图双向同步引擎"""

    def __init__(self, gps_entries: List[GPSEntry], sync_config: SyncConfig = None):
        self.gps_entries = sorted(gps_entries, key=lambda e: e.timestamp) if gps_entries else []
        self.sync_config = sync_config or SyncConfig()
        self.suppress_seek = False

    def get_position_at_time(self, time_ms: float) -> Optional[GPSEntry]:
        """
        根据时间获取插值后的 GPS 位置
        @param time_ms: 时间（毫秒）
        @return: GPS位置（插值后的GPSEntry）
        """
        entries = self.gps_entries
        if not entries:
            return None

        adjusted_time = time_ms + self.sync_config.sync_offset

        # 时间在第一个采样点之前
        if adjusted_time <= entries[0].timestamp:
            return entries[0]

        # 时间在最后一个采样点之后
        if adjusted_time >= entries[-1].timestamp:
            return entries[-1]

        # 二分查找
        lo, hi = 0, len(entries) - 1
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if entries[mid].timestamp <= adjusted_time:
                lo = mid
            else:
                hi = mid

        prev = entries[lo]
        next_entry = entries[hi]
        t = (adjusted_time - prev.timestamp) / (next_entry.timestamp - prev.timestamp) if next_entry.timestamp != prev.timestamp else 0

        mode = self.sync_config.interpolation

        if mode == 0:  # 最近邻
            return prev if t < 0.5 else next_entry

        elif mode == 1:  # 线性插值
            return GPSEntry(
                timestamp=int(adjusted_time),
                latitude=prev.latitude + (next_entry.latitude - prev.latitude) * t,
                longitude=prev.longitude + (next_entry.longitude - prev.longitude) * t,
                altitude=prev.altitude + (next_entry.altitude - prev.altitude) * t,
                accuracy=prev.accuracy,
                heading=prev.heading + (next_entry.heading - prev.heading) * t,
                speed=prev.speed + (next_entry.speed - prev.speed) * t,
            )

        elif mode == 2:  # Catmull-Rom 样条插值
            return self._catmull_rom(lo, adjusted_time)

        else:
            return prev if t < 0.5 else next_entry

    def _catmull_rom(self, idx: int, time_ms: float) -> GPSEntry:
        """Catmull-Rom 样条插值"""
        entries = self.gps_entries
        p0 = entries[max(0, idx - 1)]
        p1 = entries[idx]
        p2 = entries[idx + 1]
        p3 = entries[min(len(entries) - 1, idx + 2)]

        t = (time_ms - p1.timestamp) / (p2.timestamp - p1.timestamp) if p2.timestamp != p1.timestamp else 0
        t2 = t * t
        t3 = t2 * t

        def cr(a, b, c, d):
            return 0.5 * ((2 * b) + (-a + c) * t +
                          (2 * a - 5 * b + 4 * c - d) * t2 +
                          (-a + 3 * b - 3 * c + d) * t3)

        return GPSEntry(
            timestamp=int(time_ms),
            latitude=cr(p0.latitude, p1.latitude, p2.latitude, p3.latitude),
            longitude=cr(p0.longitude, p1.longitude, p2.longitude, p3.longitude),
            altitude=cr(p0.altitude, p1.altitude, p2.altitude, p3.altitude),
            accuracy=p1.accuracy,
            heading=p1.heading,
            speed=p1.speed,
        )

    def find_nearest_by_position(self, lat: float, lon: float) -> Optional[GPSEntry]:
        """根据经纬度查找最近的 GPS 采样点"""
        if not self.gps_entries:
            return None

        min_dist = float('inf')
        nearest = None

        for entry in self.gps_entries:
            dist = self._haversine(lat, lon, entry.latitude, entry.longitude)
            if dist < min_dist:
                min_dist = dist
                nearest = entry

        return nearest

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Haversine 距离公式（米）"""
        R = 6371000
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = math.sin(d_lat / 2) ** 2 + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(d_lon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def get_speed_color(speed: float) -> str:
        """速度热力图颜色"""
        if speed < 5:
            return '#3b82f6'   # 蓝色
        elif speed < 20:
            return '#22c55e'   # 绿色
        elif speed < 60:
            return '#eab308'   # 黄色
        elif speed < 120:
            return '#f97316'   # 橙色
        else:
            return '#ef4444'   # 红色

    def get_stats(self) -> dict:
        """计算轨迹统计信息"""
        entries = self.gps_entries
        if not entries:
            return {'distance': 0, 'max_speed': 0, 'avg_speed': 0, 'duration': 0, 'point_count': 0}

        total_dist = 0.0
        max_speed = 0.0
        total_speed = 0.0

        for i, entry in enumerate(entries):
            max_speed = max(max_speed, entry.speed)
            total_speed += entry.speed
            if i > 0:
                total_dist += self._haversine(
                    entries[i-1].latitude, entries[i-1].longitude,
                    entry.latitude, entry.longitude
                )

        duration = (entries[-1].timestamp - entries[0].timestamp) / 1000 if len(entries) > 1 else 0

        return {
            'distance': total_dist / 1000,  # km
            'max_speed': max_speed,
            'avg_speed': total_speed / len(entries),
            'duration': duration,
            'point_count': len(entries),
        }

    def get_track_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """获取轨迹的经纬度边界 (min_lat, min_lon, max_lat, max_lon)"""
        if not self.gps_entries:
            return None
        lats = [e.latitude for e in self.gps_entries]
        lons = [e.longitude for e in self.gps_entries]
        return min(lats), min(lons), max(lats), max(lons)

    def get_track_points(self) -> List[Tuple[float, float]]:
        """获取轨迹点列表 (lat, lon)"""
        return [(e.latitude, e.longitude) for e in self.gps_entries]

    def get_speed_colored_segments(self) -> List[Tuple[float, float, float, float, str]]:
        """获取按速度着色的轨迹段 (lat1, lon1, lat2, lon2, color)"""
        segments = []
        for i in range(1, len(self.gps_entries)):
            prev = self.gps_entries[i-1]
            curr = self.gps_entries[i]
            color = self.get_speed_color(curr.speed)
            segments.append((prev.latitude, prev.longitude, curr.latitude, curr.longitude, color))
        return segments
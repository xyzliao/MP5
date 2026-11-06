//
// SyncEngine.swift
// MP5Core
//
// Sync Engine — 视频↔地图双向同步引擎
//
// 职责:
// 1. 时间→位置：视频播放进度变化时，计算当前 GPS 坐标并更新地图
// 2. 位置→时间：用户点击地图时，查找最近 GPS 采样点并跳转视频
// 3. 插值：支持最近邻、线性、三次样条三种插值模式
//
// 与 Windows版 SyncEngine 和 Android版 Mp5Parser查询方法 对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation

/// 视频↔地图双向同步引擎
public class SyncEngine {

    public private(set) var gpsSamples: [GpsSample]
    public var syncRules: SyncRules

    /// 抑制seek标志（避免循环回调）
    public var suppressSeek = false

    public init(gpsSamples: [GpsSample], syncRules: SyncRules = SyncRules()) {
        self.gpsSamples = gpsSamples.sorted { $0.timestampMs < $1.timestampMs }
        self.syncRules = syncRules
    }

    /// 根据时间获取插值后的 GPS 位置
    /// - Parameter timeMs: 时间（毫秒）
    /// - Returns: GPS位置（插值后的GpsSample）
    public func getGpsAtTime(_ timeMs: Int64) -> GpsSample? {
        if gpsSamples.isEmpty { return nil }

        let adjustedTime = timeMs + Int64(syncRules.syncOffsetMs)

        // 时间在第一个采样点之前
        if adjustedTime <= gpsSamples[0].timestampMs {
            return gpsSamples[0]
        }

        // 时间在最后一个采样点之后
        if adjustedTime >= gpsSamples[gpsSamples.count - 1].timestampMs {
            return gpsSamples[gpsSamples.count - 1]
        }

        // 二分查找
        var lo = 0, hi = gpsSamples.count - 1
        while lo < hi - 1 {
            let mid = (lo + hi) / 2
            if gpsSamples[mid].timestampMs <= adjustedTime {
                lo = mid
            } else {
                hi = mid
            }
        }

        let prev = gpsSamples[lo]
        let next = gpsSamples[hi]
        let timeRange = next.timestampMs - prev.timestampMs
        if timeRange == 0 { return prev }

        let t = Double(adjustedTime - prev.timestampMs) / Double(timeRange)

        switch syncRules.interpolation {
        case 0: // 最近邻
            return t < 0.5 ? prev : next

        case 1: // 线性插值
            return GpsSample(
                timestampMs: adjustedTime,
                latitudeE7: Int64((prev.latitude + (next.latitude - prev.latitude) * t) * 10_000_000),
                longitudeE7: Int64((prev.longitude + (next.longitude - prev.longitude) * t) * 10_000_000),
                altitudeDm: Int32((prev.altitudeM + (next.altitudeM - prev.altitudeM) * t) * 10),
                accuracyM: prev.accuracyM,
                headingDeg: prev.headingDeg,
                speedKmhX10: UInt16(prev.speedKmh + (next.speedKmh - prev.speedKmh) * t)
            )

        case 2: // Catmull-Rom 样条插值
            return catmullRom(idx: lo, timeMs: adjustedTime)

        default:
            return t < 0.5 ? prev : next
        }
    }

    /// Catmull-Rom 样条插值
    private func catmullRom(idx: Int, timeMs: Int64) -> GpsSample {
        let p0 = gpsSamples[max(0, idx - 1)]
        let p1 = gpsSamples[idx]
        let p2 = gpsSamples[idx + 1]
        let p3 = gpsSamples[min(gpsSamples.count - 1, idx + 2)]

        let timeRange = p2.timestampMs - p1.timestampMs
        let t = timeRange != 0 ? Double(timeMs - p1.timestampMs) / Double(timeRange) : 0
        let t2 = t * t
        let t3 = t2 * t

        func cr(_ a: Double, _ b: Double, _ c: Double, _ d: Double) -> Double {
            0.5 * ((2 * b) + (-a + c) * t +
                   (2 * a - 5 * b + 4 * c - d) * t2 +
                   (-a + 3 * b - 3 * c + d) * t3)
        }

        return GpsSample(
            timestampMs: timeMs,
            latitudeE7: Int64(cr(p0.latitude, p1.latitude, p2.latitude, p3.latitude) * 10_000_000),
            longitudeE7: Int64(cr(p0.longitude, p1.longitude, p2.longitude, p3.longitude) * 10_000_000),
            altitudeDm: Int32(cr(p0.altitudeM, p1.altitudeM, p2.altitudeM, p3.altitudeM) * 10),
            accuracyM: p1.accuracyM,
            headingDeg: p1.headingDeg,
            speedKmhX10: p1.speedKmhX10
        )
    }

    /// 根据经纬度查找最近的 GPS 采样点时间戳
    public func findNearestTimestamp(lat: Double, lon: Double) -> Int64? {
        if gpsSamples.isEmpty { return nil }

        var minDist = Double.infinity
        var nearestTime: Int64 = 0

        for s in gpsSamples {
            let dist = haversine(lat1: lat, lon1: lon, lat2: s.latitude, lon2: s.longitude)
            if dist < minDist {
                minDist = dist
                nearestTime = s.timestampMs
            }
        }

        return nearestTime - Int64(syncRules.syncOffsetMs)
    }

    /// Haversine 距离公式（米）
    public static func haversine(lat1: Double, lon1: Double, lat2: Double, lon2: Double) -> Double {
        let R = 6_371_000.0  // 地球半径 米
        let dLat = (lat2 - lat1) * .pi / 180
        let dLon = (lon2 - lon1) * .pi / 180
        let a = sin(dLat / 2) * sin(dLat / 2) +
                cos(lat1 * .pi / 180) * cos(lat2 * .pi / 180) *
                sin(dLon / 2) * sin(dLon / 2)
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))
    }

    /// 速度热力图颜色
    public static func speedColor(_ speedKmh: Double) -> (red: Double, green: Double, blue: Double) {
        if speedKmh < 5 {
            return (0.231, 0.510, 0.965)   // 蓝色 #3b82f6
        } else if speedKmh < 20 {
            return (0.133, 0.773, 0.369)  // 绿色 #22c55e
        } else if speedKmh < 60 {
            return (0.918, 0.702, 0.031)  // 黄色 #eab308
        } else if speedKmh < 120 {
            return (0.976, 0.451, 0.086)  // 橙色 #f97316
        } else {
            return (0.937, 0.318, 0.286)  // 红色 #ef4444
        }
    }

    /// 轨迹统计信息
    public func getStats() -> [String: Double] {
        if gpsSamples.isEmpty {
            return ["distance": 0, "maxSpeed": 0, "avgSpeed": 0, "duration": 0, "pointCount": 0]
        }

        var totalDist = 0.0
        var maxSpeed = 0.0
        var totalSpeed = 0.0

        for (i, entry) in gpsSamples.enumerated() {
            maxSpeed = max(maxSpeed, entry.speedKmh)
            totalSpeed += entry.speedKmh
            if i > 0 {
                totalDist += Self.haversine(
                    lat1: gpsSamples[i - 1].latitude, lon1: gpsSamples[i - 1].longitude,
                    lat2: entry.latitude, lon2: entry.longitude
                )
            }
        }

        let duration = gpsSamples.count > 1 ?
            Double(gpsSamples[gpsSamples.count - 1].timestampMs - gpsSamples[0].timestampMs) / 1000 : 0

        return [
            "distance": totalDist / 1000,   // km
            "maxSpeed": maxSpeed,
            "avgSpeed": totalSpeed / Double(gpsSamples.count),
            "duration": duration,
            "pointCount": Double(gpsSamples.count)
        ]
    }

    /// 获取轨迹经纬度边界
    public func getTrackBounds() -> (minLat: Double, minLon: Double, maxLat: Double, maxLon: Double)? {
        if gpsSamples.isEmpty { return nil }
        let lats = gpsSamples.map { $0.latitude }
        let lons = gpsSamples.map { $0.longitude }
        return (lats.min()!, lons.min()!, lats.max()!, lons.max()!)
    }

    /// 获取按速度着色的轨迹段
    public func getSpeedColoredSegments() -> [(lat1: Double, lon1: Double, lat2: Double, lon2: Double, speed: Double)] {
        var segments = []
        for i in 1..<gpsSamples.count {
            let prev = gpsSamples[i - 1]
            let curr = gpsSamples[i]
            segments.append((prev.latitude, prev.longitude, curr.latitude, curr.longitude, curr.speedKmh))
        }
        return segments
    }
}
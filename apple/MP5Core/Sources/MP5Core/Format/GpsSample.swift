//
// GpsSample.swift
// MP5Core
//
// GPS采样点 — 对应gloc Box中的每条记录
//
// 经纬度使用整数×10^7存储，避免IEEE 754浮点精度问题。
// 例如：北纬39.9042° → 399042000
//
// 与 Windows版 GPSEntry 和 Android版 GpsSample 完全对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation

/// GPS采样点
public struct GpsSample: Codable, Identifiable, Sendable {
    public let id = UUID()
    public var timestampMs: Int64       // 毫秒，相对于mvhd时间起点
    public var latitudeE7: Int64       // 纬度 ×10^7 (WGS84)
    public var longitudeE7: Int64      // 经度 ×10^7 (WGS84)
    public var altitudeDm: Int32       // 海拔 ×10 (分米，精确到0.1米)
    public var accuracyM: UInt16       // 定位精度，米
    public var headingDeg: UInt16      // 方向角 0-360°
    public var speedKmhX10: UInt16    // 速度 km/h ×10 (精确到0.1km/h)
    public var isPoi: Bool             // 是否为POI标记点
    public var poiLabel: String?       // POI标签

    public init(
        timestampMs: Int64,
        latitudeE7: Int64,
        longitudeE7: Int64,
        altitudeDm: Int32,
        accuracyM: UInt16,
        headingDeg: UInt16,
        speedKmhX10: UInt16,
        isPoi: Bool = false,
        poiLabel: String? = nil
    ) {
        self.timestampMs = timestampMs
        self.latitudeE7 = latitudeE7
        self.longitudeE7 = longitudeE7
        self.altitudeDm = altitudeDm
        self.accuracyM = accuracyM
        self.headingDeg = headingDeg
        self.speedKmhX10 = speedKmhX10
        self.isPoi = isPoi
        self.poiLabel = poiLabel
    }

    // 便捷计算属性
    public var latitude: Double { Double(latitudeE7) / 10_000_000 }
    public var longitude: Double { Double(longitudeE7) / 10_000_000 }
    public var altitudeM: Double { Double(altitudeDm) / 10 }
    public var speedKmh: Double { Double(speedKmhX10) / 10 }
    public var heading: Double { Double(headingDeg) / 10 }

    /// 从度数创建采样点
    public static func fromDegrees(
        timestampMs: Int64,
        latitude: Double,
        longitude: Double,
        altitudeM: Double,
        accuracyM: Int,
        headingDeg: Int,
        speedKmh: Double
    ) -> GpsSample {
        GpsSample(
            timestampMs: timestampMs,
            latitudeE7: Int64(latitude * 10_000_000),
            longitudeE7: Int64(longitude * 10_000_000),
            altitudeDm: Int32(altitudeM * 10),
            accuracyM: UInt16(min(max(accuracyM, 0), 65535)),
            headingDeg: UInt16(min(max(headingDeg, 0), 3600)),
            speedKmhX10: UInt16(min(max(Int(speedKmh * 10), 0), 65535))
        )
    }

    /// 编码为34字节二进制（gloc Box条目）
    /// timestamp(8B) + latitude(8B) + longitude(8B) + altitude(4B signed) +
    /// accuracy(2B) + heading(2B) + speed(2B) = 34 bytes
    public func encode() -> Data {
        var data = Data()
        data.appendInt64BE(timestampMs)
        data.appendInt64BE(latitudeE7)
        data.appendInt64BE(longitudeE7)
        data.appendInt32BE(altitudeDm)
        data.appendUInt16BE(accuracyM)
        data.appendUInt16BE(headingDeg)
        data.appendUInt16BE(speedKmhX10)
        return data
    }

    /// 从二进制解码
    public static func decode(data: Data, offset: Int) -> GpsSample? {
        guard offset + 34 <= data.count else { return nil }
        return GpsSample(
            timestampMs: data.readInt64BE(at: offset),
            latitudeE7: data.readInt64BE(at: offset + 8),
            longitudeE7: data.readInt64BE(at: offset + 16),
            altitudeDm: data.readInt32BE(at: offset + 24),
            accuracyM: UInt16(data.readUInt16BE(at: offset + 28)),
            headingDeg: UInt16(data.readUInt16BE(at: offset + 30)),
            speedKmhX10: UInt16(data.readUInt16BE(at: offset + 32))
        )
    }
}

/// gloc Box 单条目大小
public let GLOC_ENTRY_SIZE = 34
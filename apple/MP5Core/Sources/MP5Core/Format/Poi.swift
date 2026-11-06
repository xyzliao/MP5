//
// Poi.swift
// MP5Core
//
// POI 标记数据结构 — 对应gpoi Box中的条目
//
// 与 Windows版 POI 和 Android版 gpoi解析 完全对齐。
//
// 格式：
//   timestamp(8B) + latitudeE7(8B) + longitudeE7(8B) +
//   label_length(2B) + label_bytes(UTF-8) + type(1B)
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation

/// POI 标记
public struct Poi: Codable, Identifiable, Sendable {
    public let id = UUID()
    public var timestampMs: Int64
    public var latitudeE7: Int64
    public var longitudeE7: Int64
    public var label: String
    public var type: String

    public init(timestampMs: Int64, latitude: Double, longitude: Double, label: String = "", type: String = "poi") {
        self.timestampMs = timestampMs
        self.latitudeE7 = Int64(latitude * 10_000_000)
        self.longitudeE7 = Int64(longitude * 10_000_000)
        self.label = label
        self.type = type
    }

    public var latitude: Double { Double(latitudeE7) / 10_000_000 }
    public var longitude: Double { Double(longitudeE7) / 10_000_000 }

    /// 编码为二进制
    public func encode() -> Data {
        var data = Data()
        data.appendInt64BE(timestampMs)
        data.appendInt64BE(latitudeE7)
        data.appendInt64BE(longitudeE7)
        let labelBytes = Data(label.utf8)
        data.appendUInt16BE(UInt16(labelBytes.count))
        data.append(labelBytes)
        data.appendUInt8(type.isEmpty ? 0 : Int(type.utf8.first!.asciiValue ?? 0))
        return data
    }

    /// 从二进制解码，返回POI和下一个偏移
    public static func decode(data: Data, offset: Int) -> (Poi, Int)? {
        guard offset + 24 <= data.count else { return nil }
        let ts = data.readInt64BE(at: offset)
        let lat = data.readInt64BE(at: offset + 8)
        let lon = data.readInt64BE(at: offset + 16)
        var pos = offset + 24

        guard pos + 2 <= data.count else { return nil }
        let labelLen = data.readUInt16BE(at: pos)
        pos += 2

        guard pos + labelLen <= data.count else { return nil }
        let label = String(data: data[pos..<(pos + labelLen)], encoding: .utf8) ?? ""
        pos += labelLen

        guard pos < data.count else { return nil }
        let typeByte = data[pos]
        pos += 1

        let poi = Poi(
            timestampMs: ts,
            latitude: Double(lat) / 10_000_000,
            longitude: Double(lon) / 10_000_000,
            label: label,
            type: typeByte != 0 ? String(UnicodeScalar(typeByte)) : "poi"
        )
        return (poi, pos)
    }
}
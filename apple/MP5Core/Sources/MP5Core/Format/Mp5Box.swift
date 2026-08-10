//
// Mp5Box.swift
// MP5Core
//
// MP5 Box — ISO BMFF (ISO 14496-12) Box 读写工具
//
// MP5基于ISO Base Media File Format，通过新增自定义Box类型扩展MP4：
//   gloc - GPS坐标轨迹
//   gmap - 嵌入地图数据
//   gsyn - 同步规则
//   gpoi - POI标记数据
//
// Box结构：
//   [size(4)] [type(4)] [payload(size-8)]
//   FullBox:  [size(4)] [type(4)] [version(1)] [flags(3)] [payload]
//
// 与 Windows版 mp5_box.py 和 Android版 Mp5Box.kt 完全对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import Foundation

/// Box类型常量
public enum Mp5BoxType {
    public static let FTYP = "ftyp"
    public static let MOOV = "moov"
    public static let MVHD = "mvhd"
    public static let TRAK = "trak"
    public static let MDAT = "mdat"
    public static let META = "meta"
    public static let HDLR = "hdlr"
    public static let GLOC = "gloc"   // GPS坐标轨迹
    public static let GMAP = "gmap"   // 嵌入地图数据
    public static let GSYN = "gsyn"   // 同步规则
    public static let GPOI = "gpoi"   // POI标记数据
    public static let STCO = "stco"   // 32位 chunk offset
    public static let CO64 = "co64"   // 64位 chunk offset
}

/// 容器Box类型（包含子Box）
private let CONTAINER_TYPES: Set<String> = [
    "moov", "trak", "mdia", "minf", "stbl", "meta", "udta", "edts"
]

/// FullBox类型（含version和flags）
private let FULLBOX_TYPES: Set<String> = [
    "gloc", "gmap", "gsyn", "gpoi", "mvhd", "tkhd", "mdhd", "hdlr", "meta", "stco", "co64"
]

/// ISO BMFF Box 结构
public struct Mp5Box: Identifiable {
    public let id = UUID()
    public let type: String
    public let offset: Int        // 在文件中的绝对偏移
    public let size: Int          // 完整Box大小（含header）
    public let dataOffset: Int    // payload起始偏移
    public let dataSize: Int      // payload大小
    public var version: Int?
    public var flags: Int?
    public var children: [Mp5Box] = []

    public var isContainer: Bool { CONTAINER_TYPES.contains(type) }
    public var isFullBox: Bool { FULLBOX_TYPES.contains(type) }
}

/// Box 读写辅助工具
public enum Mp5BoxIO {

    // MARK: - 读取

    /// 递归解析 Box 结构
    public static func parseBoxes(_ data: Data, start: Int = 0, end: Int? = nil) -> [Mp5Box] {
        let endOffset = end ?? data.count
        var boxes: [Mp5Box] = []
        var offset = start

        while offset + 8 <= endOffset {
            let boxStart = offset
            var size = data.readUInt32BE(at: offset)
            let boxType = data.readStringASCII(at: offset + 4, length: 4)
            var headerSize = 8

            if size == 1 {
                // 64-bit extended size
                size = Int(data.readUInt64BE(at: offset + 8))
                headerSize = 16
            } else if size == 0 {
                // box extends to end
                size = endOffset - boxStart
            }

            let dataOffset = boxStart + headerSize
            let dataSize = size - headerSize

            var box = Mp5Box(
                type: boxType,
                offset: boxStart,
                size: size,
                dataOffset: dataOffset,
                dataSize: dataSize,
                version: nil,
                flags: nil
            )

            // FullBox: 解析 version 和 flags
            if FULLBOX_TYPES.contains(boxType) && dataSize >= 4 {
                box.version = Int(data[dataOffset])
                box.flags = (Int(data[dataOffset + 1]) << 16) |
                            (Int(data[dataOffset + 2]) << 8) |
                            Int(data[dataOffset + 3])
            }

            // 容器Box: 递归解析子Box
            if CONTAINER_TYPES.contains(boxType) {
                box.children = parseBoxes(data, start: dataOffset, end: boxStart + size)
            }

            boxes.append(box)
            offset = boxStart + size
        }

        return boxes
    }

    /// 递归查找指定类型的 Box
    public static func findBox(in boxes: [Mp5Box], type: String) -> Mp5Box? {
        for box in boxes {
            if box.type == type { return box }
            if let found = findBox(in: box.children, type: type) {
                return found
            }
        }
        return nil
    }

    /// 查找所有指定类型的 Box
    public static func findAllBoxes(in boxes: [Mp5Box], type: String) -> [Mp5Box] {
        var results: [Mp5Box] = []
        for box in boxes {
            if box.type == type { results.append(box) }
            results.append(contentsOf: findAllBoxes(in: box.children, type: type))
        }
        return results
    }

    // MARK: - 写入

    /// 写入标准 Box
    public static func buildBox(type: String, payload: Data) -> Data {
        var result = Data()
        let size = UInt32(8 + payload.count)
        result.appendUInt32BE(size)
        result.append(type: type)
        result.append(payload)
        return result
    }

    /// 写入 FullBox (含 version 和 flags)
    public static func buildFullBox(type: String, version: Int = 0, flags: Int = 0, payload: Data) -> Data {
        var result = Data()
        let size = UInt32(12 + payload.count)
        result.appendUInt32BE(size)
        result.append(type: type)
        let vf = UInt32((version << 24) | (flags & 0xFFFFFF))
        result.appendUInt32BE(vf)
        result.append(payload)
        return result
    }

    /// 写入 ftyp Box
    public static func buildFtyp(majorBrand: String = "mp5v",
                                  minorVersion: UInt32 = 0,
                                  compatibleBrands: [String] = ["mp5v", "mp41", "isom"]) -> Data {
        var payload = Data()
        payload.append(type: majorBrand)
        payload.appendUInt32BE(minorVersion)
        for brand in compatibleBrands {
            payload.append(type: brand)
        }
        return buildBox(type: Mp5BoxType.FTYP, payload: payload)
    }
}

// MARK: - Data 扩展

extension Data {
    /// 读取大端 UInt32
    func readUInt32BE(at offset: Int) -> Int {
        guard offset + 4 <= count else { return 0 }
        return Int(self[offset]) << 24 |
               Int(self[offset + 1]) << 16 |
               Int(self[offset + 2]) << 8 |
               Int(self[offset + 3])
    }

    /// 读取大端 UInt64
    func readUInt64BE(at offset: Int) -> Int {
        guard offset + 8 <= count else { return 0 }
        var value: UInt64 = 0
        for i in 0..<8 {
            value = (value << 8) | UInt64(self[offset + i])
        }
        return Int(value)
    }

    /// 读取大端 Int64
    func readInt64BE(at offset: Int) -> Int64 {
        guard offset + 8 <= count else { return 0 }
        var value: Int64 = 0
        for i in 0..<8 {
            value = (value << 8) | Int64(self[offset + i])
        }
        return value
    }

    /// 读取大端 Int32
    func readInt32BE(at offset: Int) -> Int32 {
        guard offset + 4 <= count else { return 0 }
        return Int32(bitPattern: UInt32(readUInt32BE(at: offset)))
    }

    /// 读取大端 UInt16
    func readUInt16BE(at offset: Int) -> Int {
        guard offset + 2 <= count else { return 0 }
        return Int(self[offset]) << 8 | Int(self[offset + 1])
    }

    /// 读取大端 Float32
    func readFloat32BE(at offset: Int) -> Float {
        guard offset + 4 <= count else { return 0 }
        let bits = UInt32(readUInt32BE(at: offset))
        return Float(bitPattern: bits)
    }

    /// 读取 ASCII 字符串
    func readStringASCII(at offset: Int, length: Int) -> String {
        guard offset + length <= count else { return "" }
        let bytes = self[offset..<(offset + length)]
        return String(data: bytes, encoding: .ascii) ?? ""
    }

    /// 追加大端 UInt32
    mutating func appendUInt32BE(_ value: UInt32) {
        append(UInt8((value >> 24) & 0xFF))
        append(UInt8((value >> 16) & 0xFF))
        append(UInt8((value >> 8) & 0xFF))
        append(UInt8(value & 0xFF))
    }

    /// 追加大端 Int32
    mutating func appendInt32BE(_ value: Int32) {
        appendUInt32BE(UInt32(bitPattern: value))
    }

    /// 追加大端 UInt64
    mutating func appendUInt64BE(_ value: UInt64) {
        for i in (0..<8).reversed() {
            append(UInt8((value >> UInt64(i * 8)) & 0xFF))
        }
    }

    /// 追加大端 Int64
    mutating func appendInt64BE(_ value: Int64) {
        appendUInt64BE(UInt64(bitPattern: value))
    }

    /// 追加大端 UInt16
    mutating func appendUInt16BE(_ value: UInt16) {
        append(UInt8((value >> 8) & 0xFF))
        append(UInt8(value & 0xFF))
    }

    /// 追加大端 Float32
    mutating func appendFloat32BE(_ value: Float) {
        appendUInt32BE(value.bitPattern)
    }

    /// 追加4字符类型码
    mutating func append(type: String) {
        let bytes = type.utf8
        for i in 0..<4 {
            append(i < bytes.count ? bytes[bytes.index(bytes.startIndex, offsetBy: i)] : 0)
        }
    }

    /// 追加单字节
    mutating func appendUInt8(_ value: Int) {
        append(UInt8(value & 0xFF))
    }
}
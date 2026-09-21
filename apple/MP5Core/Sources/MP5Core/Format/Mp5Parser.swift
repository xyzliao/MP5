//
// Mp5Parser.swift
// MP5Core
//
// MP5 文件解析器 — 解析 MP5 文件，提取视频轨道、GPS轨迹、同步规则等元数据
//
// 1. 读取ftyp确认是MP5文件（major_brand=mp5v）
// 2. 查找 gloc、gsyn、gpoi、gmap box
// 3. 解析GPS采样点列表
// 4. 向后兼容：如果无gloc box，则按普通MP4处理
//
// 与 Windows版 MP5Parser 和 Android版 Mp5Parser 完全对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation

/// 轨道信息
public struct TrackInfo: Sendable {
    public var trackId: Int = 0
    public var trackType: String = "unknown"  // video / audio / metadata
    public var duration: Int = 0
    public var timescale: Int = 0
    public var width: Int = 0
    public var height: Int = 0
}

/// MP5文件解析结果
public struct Mp5Info: Sendable {
    public var isMp5: Bool = false
    public var majorBrand: String = ""
    public var compatibleBrands: [String] = []
    public var durationMs: Double = 0
    public var timescale: Int = 0
    public var tracks: [TrackInfo] = []
    public var gpsSamples: [GpsSample] = []
    public var syncRules: SyncRules = SyncRules()
    public var pois: [Poi] = []
    public var hasMapData: Bool = false
    public var fileSize: Int = 0
}

/// MP5文件解析器
public class Mp5Parser {

    /// 解析 MP5 文件数据，返回 Mp5Info
    public static func parse(_ data: Data) -> Mp5Info {
        var info = Mp5Info(fileSize: data.count)
        let boxes = Mp5BoxIO.parseBoxes(data)

        // 解析 ftyp
        if let ftyp = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.FTYP) {
            let ftypData = data.subdata(in: ftyp.dataOffset..<(ftyp.dataOffset + ftyp.dataSize))
            if ftypData.count >= 8 {
                info.majorBrand = ftypData.readStringASCII(at: 0, length: 4)
                if info.majorBrand == "mp5v" {
                    info.isMp5 = true
                }
                // compatible_brands
                var offset = 8  // skip major_brand(4) + minor_version(4)
                while offset + 4 <= ftypData.count {
                    let brand = ftypData.readStringASCII(at: offset, length: 4)
                    info.compatibleBrands.append(brand)
                    if brand == "mp5v" {
                        info.isMp5 = true
                    }
                    offset += 4
                }
            }
        }

        // 解析 moov
        if let moov = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.MOOV) {
            // mvhd
            if let mvhd = Mp5BoxIO.findBox(in: moov.children, type: Mp5BoxType.MVHD),
               mvhd.dataSize >= 4 {
                let mvhdData = data.subdata(in: (mvhd.dataOffset + 4)..<(mvhd.dataOffset + mvhd.dataSize))
                let version = mvhd.version ?? 0
                if version == 1 && mvhdData.count >= 28 {
                    info.timescale = mvhdData.readUInt32BE(at: 8)
                    let duration = mvhdData.readUInt64BE(at: 12)
                    if info.timescale > 0 {
                        info.durationMs = Double(duration) / Double(info.timescale) * 1000
                    }
                } else if mvhdData.count >= 20 {
                    info.timescale = mvhdData.readUInt32BE(at: 8)
                    let duration = mvhdData.readUInt32BE(at: 12)
                    if info.timescale > 0 {
                        info.durationMs = Double(duration) / Double(info.timescale) * 1000
                    }
                }
            }

            // traks
            for trak in Mp5BoxIO.findAllBoxes(in: moov.children, type: Mp5BoxType.TRAK) {
                if let track = parseTrak(data: data, trak: trak) {
                    info.tracks.append(track)
                }
            }
        }

        // 解析 gloc (GPS轨迹)
        if let gloc = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GLOC) {
            info.gpsSamples = parseGloc(data: data, box: gloc)
            if !info.gpsSamples.isEmpty {
                info.isMp5 = true
            }
        }

        // 解析 gsyn (同步规则)
        if let gsyn = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GSYN) {
            // FullBox: payload starts after version+flags (4 bytes)
            let payloadOffset = gsyn.dataOffset + 4
            if let rules = SyncRules.decode(data: data, offset: payloadOffset) {
                info.syncRules = rules
            }
        }

        // 解析 gpoi (POI标记)
        if let gpoi = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GPOI) {
            info.pois = parseGpoi(data: data, box: gpoi)
        }

        // 检查 gmap
        if Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.GMAP) != nil {
            info.hasMapData = true
        }

        return info
    }

    /// 解析单个 trak box
    private static func parseTrak(data: Data, trak: Mp5Box) -> TrackInfo? {
        guard let tkhd = Mp5BoxIO.findBox(in: trak.children, type: "tkhd"),
              let mdia = Mp5BoxIO.findBox(in: trak.children, type: "mdia") else {
            return nil
        }

        var track = TrackInfo()
        let version = tkhd.version ?? 0
        let tkhdData = data.subdata(in: (tkhd.dataOffset + 4)..<(tkhd.dataOffset + tkhd.dataSize))

        if version == 1 && tkhdData.count >= 32 {
            track.trackId = tkhdData.readUInt32BE(at: 8)
            track.duration = tkhdData.readUInt64BE(at: 16)
        } else if tkhdData.count >= 20 {
            track.trackId = tkhdData.readUInt32BE(at: 8)
            track.duration = tkhdData.readUInt32BE(at: 12)
        }

        // mdhd (timescale)
        if let mdhd = Mp5BoxIO.findBox(in: mdia.children, type: "mdhd"),
           mdhd.dataSize >= 4 {
            let mdhdData = data.subdata(in: (mdhd.dataOffset + 4)..<(mdhd.dataOffset + mdhd.dataSize))
            let v = mdhd.version ?? 0
            if v == 1 && mdhdData.count >= 28 {
                track.timescale = mdhdData.readUInt32BE(at: 8)
            } else if mdhdData.count >= 20 {
                track.timescale = mdhdData.readUInt32BE(at: 8)
            }
        }

        // hdlr (track type)
        if let hdlr = Mp5BoxIO.findBox(in: mdia.children, type: Mp5BoxType.HDLR),
           hdlr.dataSize >= 12 {
            let hdlrData = data.subdata(in: (hdlr.dataOffset + 4)..<(hdlr.dataOffset + hdlr.dataSize))
            if hdlrData.count >= 8 {
                let handlerType = hdlrData.readStringASCII(at: 4, length: 4)
                track.trackType = ["vide": "video", "soun": "audio", "meta": "metadata"][handlerType] ?? handlerType
            }
        }

        // video track: width/height from tkhd
        if track.trackType == "video" {
            if version == 0 && tkhdData.count >= 92 {
                track.width = tkhdData.readUInt32BE(at: 84) >> 16
                track.height = tkhdData.readUInt32BE(at: 88) >> 16
            } else if version == 1 && tkhdData.count >= 108 {
                track.width = tkhdData.readUInt32BE(at: 100) >> 16
                track.height = tkhdData.readUInt32BE(at: 104) >> 16
            }
        }

        return track
    }

    /// 解析 gloc Box，返回GPS采样点列表
    /// FullBox: skip version(1) + flags(3) = 4 bytes, then entry_count(4), then entries
    private static func parseGloc(data: Data, box: Mp5Box) -> [GpsSample] {
        let payloadOffset = box.dataOffset + 4  // skip version+flags
        guard payloadOffset + 4 <= box.dataOffset + box.dataSize else { return [] }

        let entryCount = data.readUInt32BE(at: payloadOffset)
        var offset = payloadOffset + 4
        var samples: [GpsSample] = []

        for _ in 0..<entryCount {
            guard offset + GLOC_ENTRY_SIZE <= data.count else { break }
            if let sample = GpsSample.decode(data: data, offset: offset) {
                samples.append(sample)
            }
            offset += GLOC_ENTRY_SIZE
        }

        return samples
    }

    /// 解析 gpoi Box，返回POI列表
    private static func parseGpoi(data: Data, box: Mp5Box) -> [Poi] {
        let payloadOffset = box.dataOffset + 4  // skip version+flags
        guard payloadOffset + 4 <= box.dataOffset + box.dataSize else { return [] }

        let poiCount = data.readUInt32BE(at: payloadOffset)
        var offset = payloadOffset + 4
        var pois: [Poi] = []

        for _ in 0..<poiCount {
            guard let (poi, nextOffset) = Poi.decode(data: data, offset: offset) else { break }
            pois.append(poi)
            offset = nextOffset
        }

        return pois
    }

    // MARK: - 便捷查询方法

    /// 获取指定时间的GPS位置（含插值）
    public static func getGpsAtTime(samples: [GpsSample], timeMs: Int64, syncRules: SyncRules) -> (Double, Double)? {
        if samples.isEmpty { return nil }
        if samples.count == 1 { return (samples[0].latitude, samples[0].longitude) }

        let adjustedTime = timeMs + Int64(syncRules.syncOffsetMs)

        // 早于第一个采样点
        if adjustedTime <= samples[0].timestampMs {
            return (samples[0].latitude, samples[0].longitude)
        }
        // 晚于最后一个采样点
        if adjustedTime >= samples[samples.count - 1].timestampMs {
            return (samples[samples.count - 1].latitude, samples[samples.count - 1].longitude)
        }

        // 二分查找
        var lo = 0, hi = samples.count - 1
        while lo < hi - 1 {
            let mid = (lo + hi) / 2
            if samples[mid].timestampMs < adjustedTime {
                lo = mid
            } else if samples[mid].timestampMs > adjustedTime {
                hi = mid
            } else {
                return (samples[mid].latitude, samples[mid].longitude)
            }
        }

        let before = samples[lo]
        let after = samples[hi]
        let timeRange = after.timestampMs - before.timestampMs
        if timeRange == 0 { return (before.latitude, before.longitude) }

        switch syncRules.interpolation {
        case 0: // 最近邻
            if adjustedTime - before.timestampMs < after.timestampMs - adjustedTime {
                return (before.latitude, before.longitude)
            } else {
                return (after.latitude, after.longitude)
            }
        default: // 线性插值
            let t = Double(adjustedTime - before.timestampMs) / Double(timeRange)
            let lat = before.latitude + (after.latitude - before.latitude) * t
            let lon = before.longitude + (after.longitude - before.longitude) * t
            return (lat, lon)
        }
    }

    /// 查找距离指定坐标最近的采样点的时间戳
    public static func getNearestTimestamp(samples: [GpsSample], lat: Double, lon: Double, syncOffsetMs: Int = 0) -> Int64? {
        if samples.isEmpty { return nil }
        var minDist = Double.infinity
        var nearestTime: Int64 = 0
        for s in samples {
            let dLat = s.latitude - lat
            let dLon = s.longitude - lon
            let dist = dLat * dLat + dLon * dLon
            if dist < minDist {
                minDist = dist
                nearestTime = s.timestampMs
            }
        }
        return nearestTime - Int64(syncOffsetMs)
    }

    /// 获取轨迹总距离（公里）
    public static func getTotalDistance(samples: [GpsSample]) -> Double {
        if samples.count < 2 { return 0 }
        var total = 0.0
        for i in 1..<samples.count {
            total += haversineKm(
                lat1: samples[i - 1].latitude, lon1: samples[i - 1].longitude,
                lat2: samples[i].latitude, lon2: samples[i].longitude
            )
        }
        return total
    }

    /// 获取最大速度
    public static func getMaxSpeed(samples: [GpsSample]) -> Double {
        samples.map { $0.speedKmh }.max() ?? 0
    }

    /// Haversine 距离公式（公里）
    public static func haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double) -> Double {
        let r = 6371.0  // 地球半径 km
        let dLat = (lat2 - lat1) * .pi / 180
        let dLon = (lon2 - lon1) * .pi / 180
        let a = sin(dLat / 2) * sin(dLat / 2) +
                cos(lat1 * .pi / 180) * cos(lat2 * .pi / 180) *
                sin(dLon / 2) * sin(dLon / 2)
        let c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c
    }
}
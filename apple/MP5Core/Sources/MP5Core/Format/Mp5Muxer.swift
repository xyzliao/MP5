//
// Mp5Muxer.swift
// MP5Core
//
// MP5 Muxer — 将GPS轨迹数据封装进MP4文件，生成MP5
//
// 流程：
// 1. 写入 MP5 ftyp (major_brand = mp5v)
// 2. 写入原始 moov box
// 3. 写入 gloc/gpoi/gsyn box (MP5扩展)
// 4. 写入 mdat box
// 5. 修正 moov 中 stco/co64 的偏移量
//
// 兼容性：不支持MP5的播放器会忽略gloc/gsyn，按mp41/isom正常播放视频
//
// 与 Windows版 mux_mp5() 和 Android版 Mp5Muxer 完全对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation

/// MP5 文件封装器
public class Mp5Muxer {

    // GPS采样点
    private var gpsSamples: [GpsSample] = []

    // POI标记点
    private var pois: [Poi] = []

    // gsyn 配置
    public var syncMode: Int = 0
    public var syncOffsetMs: Int = 0
    public var interpolation: Int = 1
    public var defaultView: Int = 2
    public var videoRatio: Float = 0.5
    public var mapStyle: Int = 0
    public var showTrajectory: Bool = true
    public var showPoi: Bool = true

    // MARK: - 添加数据

    public func addGpsSample(_ sample: GpsSample) {
        gpsSamples.append(sample)
    }

    public func addGpsSamples(_ samples: [GpsSample]) {
        gpsSamples.append(contentsOf: samples)
    }

    public func addPois(_ pois: [Poi]) {
        self.pois.append(contentsOf: pois)
    }

    // MARK: - 构建 Box

    /// 构建 gloc Box
    private func buildGlocBox() -> Data {
        var payload = Data()
        payload.appendUInt32BE(UInt32(gpsSamples.count))
        for s in gpsSamples {
            payload.append(s.encode())
        }
        return Mp5BoxIO.buildFullBox(type: Mp5BoxType.GLOC, version: 0, flags: 0, payload: payload)
    }

    /// 构建 gpoi Box
    private func buildGpoiBox() -> Data {
        var payload = Data()
        payload.appendUInt32BE(UInt32(pois.count))
        for p in pois {
            payload.append(p.encode())
        }
        return Mp5BoxIO.buildFullBox(type: Mp5BoxType.GPOI, version: 0, flags: 0, payload: payload)
    }

    /// 构建 gsyn Box
    private func buildGsynBox() -> Data {
        let rules = SyncRules(
            syncMode: syncMode,
            syncOffsetMs: syncOffsetMs,
            interpolation: interpolation,
            defaultView: defaultView,
            videoRatio: videoRatio,
            mapStyle: mapStyle,
            showTrajectory: showTrajectory,
            showPoi: showPoi
        )
        return Mp5BoxIO.buildFullBox(type: Mp5BoxType.GSYN, version: 0, flags: 0, payload: rules.encode())
    }

    // MARK: - 封装

    /// 将 MP4 数据 + GPS 数据封装为 MP5 文件
    /// - Parameters:
    ///   - mp4Data: 原始 MP4 文件数据
    ///   - gpsSamples: GPS采样点列表
    ///   - syncRules: 同步规则
    ///   - pois: POI标记列表
    /// - Returns: MP5 文件数据
    public func mux(mp4Data: Data, gpsSamples: [GpsSample] = [], syncRules: SyncRules? = nil, pois: [Poi] = []) -> Data {
        if !gpsSamples.isEmpty { self.gpsSamples = gpsSamples }
        if !pois.isEmpty { self.pois = pois }
        if let rules = syncRules {
            self.syncMode = rules.syncMode
            self.syncOffsetMs = rules.syncOffsetMs
            self.interpolation = rules.interpolation
            self.defaultView = rules.defaultView
            self.videoRatio = rules.videoRatio
            self.mapStyle = rules.mapStyle
            self.showTrajectory = rules.showTrajectory
            self.showPoi = rules.showPoi
        }

        // 解析原始 MP4 box 结构
        let boxes = Mp5BoxIO.parseBoxes(mp4Data)
        let moovBox = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.MOOV)
        let mdatBox = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.MDAT)

        // 计算原始 mdat 的数据偏移
        let origMdatDataOffset = mdatBox?.dataOffset ?? 0

        var result = Data()

        // 1. 写入 MP5 ftyp (major_brand = mp5v)
        result.append(Mp5BoxIO.buildFtyp())

        // 2. 写入原始 moov box
        if let moov = moovBox {
            result.append(mp4Data.subdata(in: moov.offset..<(moov.offset + moov.size)))
        }

        // 3. 写入 gloc box (GPS轨迹)
        if !self.gpsSamples.isEmpty {
            result.append(buildGlocBox())
        }

        // 4. 写入 gpoi box (POI标记)
        if !self.pois.isEmpty {
            result.append(buildGpoiBox())
        }

        // 5. 写入 gsyn box (同步规则)
        result.append(buildGsynBox())

        // 6. 写入 mdat box (媒体数据)
        if let mdat = mdatBox {
            result.append(mp4Data.subdata(in: mdat.offset..<(mdat.offset + mdat.size)))
        } else {
            result.append(mp4Data)
        }

        // 7. 修正 stco 偏移量
        let newBoxes = Mp5BoxIO.parseBoxes(result)
        let newMdat = Mp5BoxIO.findBox(in: newBoxes, type: Mp5BoxType.MDAT)
        let newMdatDataOffset = newMdat?.dataOffset ?? 0
        let delta = newMdatDataOffset - origMdatDataOffset

        if delta != 0 {
            result = fixStcoOffsets(data: result, delta: delta)
        }

        return result
    }

    /// 将 MP4 文件转换为 MP5 文件
    /// - Parameters:
    ///   - mp4File: 输入的MP4文件
    ///   - mp5File: 输出的MP5文件
    public func muxFile(mp4File: URL, mp5File: URL) throws {
        let mp4Data = try Data(contentsOf: mp4File)
        let mp5Data = mux(mp4Data: mp4Data)
        try mp5Data.write(to: mp5File)
    }

    // MARK: - stco/co64 偏移修正

    /// 修正 moov 中 stco/co64 表的绝对偏移量
    /// 当 mdat 在文件中的位置发生变化时，stco 中的偏移需要加上 delta
    private func fixStcoOffsets(data: Data, delta: Int) -> Data {
        if delta == 0 { return data }

        let boxes = Mp5BoxIO.parseBoxes(data)
        guard let moov = Mp5BoxIO.findBox(in: boxes, type: Mp5BoxType.MOOV) else { return data }

        // 查找所有 stco 和 co64 box
        let stcoBoxes = Mp5BoxIO.findAllBoxes(in: moov.children, type: Mp5BoxType.STCO) +
                       Mp5BoxIO.findAllBoxes(in: moov.children, type: Mp5BoxType.CO64)

        if stcoBoxes.isEmpty { return data }

        var mutableData = data

        for stco in stcoBoxes {
            // FullBox: 8-byte header + 4-byte version/flags + 4-byte entry_count + entries
            let payloadStart = stco.offset + 12  // 8 header + 4 version/flags
            let entryCount = mutableData.readUInt32BE(at: payloadStart)

            if stco.type == Mp5BoxType.STCO {
                // stco: 每个条目4字节
                for i in 0..<entryCount {
                    let entryPos = payloadStart + 4 + i * 4
                    let oldVal = mutableData.readUInt32BE(at: entryPos)
                    let newVal = oldVal + delta
                    mutableData.replaceBytes(
                        at: entryPos,
                        with: Data([
                            UInt8((newVal >> 24) & 0xFF),
                            UInt8((newVal >> 16) & 0xFF),
                            UInt8((newVal >> 8) & 0xFF),
                            UInt8(newVal & 0xFF)
                        ])
                    )
                }
            } else if stco.type == Mp5BoxType.CO64 {
                // co64: 每个条目8字节
                for i in 0..<entryCount {
                    let entryPos = payloadStart + 4 + i * 8
                    let oldVal = UInt64(mutableData.readUInt64BE(at: entryPos))
                    let newVal = oldVal + UInt64(delta)
                    var bytes = Data()
                    for j in (0..<8).reversed() {
                        bytes.append(UInt8((newVal >> UInt64(j * 8)) & 0xFF))
                    }
                    mutableData.replaceBytes(at: entryPos, with: bytes)
                }
            }
        }

        return mutableData
    }
}

// MARK: - Data 扩展：replaceBytes

extension Data {
    mutating func replaceBytes(at offset: Int, with newBytes: Data) {
        guard offset + newBytes.count <= count else { return }
        newBytes.withUnsafeBytes { srcBuf in
            self.withUnsafeMutableBytes { dstBuf in
                if let srcBase = srcBuf.baseAddress, let dstBase = dstBuf.baseAddress {
                    memcpy(dstBase.advanced(by: offset), srcBase, newBytes.count)
                }
            }
        }
    }
}
//
// SyncRules.swift
// MP5Core
//
// gsyn Box 同步规则
//
// 与 Windows版 SyncConfig 和 Android版 SyncRules 完全对齐。
// 字段顺序：sync_mode(1B) + sync_offset(4B) + interpolation(1B) + video_ratio(4B) +
//           map_style(1B) + show_trajectory(1B) + show_poi(1B) + default_view(1B) = 14 bytes
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation

/// 同步模式
public enum SyncMode: Int, Codable, Sendable {
    case timeSync = 0      // 时间同步
    case nearestNeighbor = 1  // 最近邻
    case interpolation = 2    // 插值
}

/// 插值算法
public enum Interpolation: Int, Codable, Sendable {
    case nearest = 0    // 最近邻
    case linear = 1     // 线性
    case cubicSpline = 2  // 三次样条
}

/// 地图样式
public enum MapStyle: Int, Codable, Sendable {
    case standard = 0
    case satellite = 1
    case terrain = 2
    case dark = 3
}

/// 视图模式
public enum ViewMode: Int, Codable, CaseIterable, Sendable {
    case videoOnly = 0
    case mapOnly = 1
    case splitLR = 2      // 分屏左右
    case splitTB = 3      // 分屏上下
    case pip = 4         // 画中画
}

/// gsyn Box 同步规则
public struct SyncRules: Codable, Sendable {
    public var syncMode: Int       // 0=时间同步, 1=最近邻, 2=插值
    public var syncOffsetMs: Int   // 同步偏移量(毫秒)
    public var interpolation: Int // 0=最近邻, 1=线性, 2=三次样条
    public var defaultView: Int   // 0=仅视频, 1=仅地图, 2=分屏左右, 3=分屏上下, 4=画中画
    public var videoRatio: Float  // 分屏视频占比
    public var mapStyle: Int      // 0=标准, 1=卫星, 2=地形, 3=暗色
    public var showTrajectory: Bool
    public var showPoi: Bool

    public init(
        syncMode: Int = 0,
        syncOffsetMs: Int = 0,
        interpolation: Int = 1,
        defaultView: Int = 2,
        videoRatio: Float = 0.5,
        mapStyle: Int = 0,
        showTrajectory: Bool = true,
        showPoi: Bool = true
    ) {
        self.syncMode = syncMode
        self.syncOffsetMs = syncOffsetMs
        self.interpolation = interpolation
        self.defaultView = defaultView
        self.videoRatio = videoRatio
        self.mapStyle = mapStyle
        self.showTrajectory = showTrajectory
        self.showPoi = showPoi
    }

    /// 编码为14字节二进制
    /// 与 Windows版 struct.pack('>BiBfBBBB', ...) 对齐
    public func encode() -> Data {
        var data = Data()
        data.appendUInt8(syncMode)           // sync_mode(1B)
        data.appendInt32BE(Int32(syncOffsetMs))  // sync_offset(4B)
        data.appendUInt8(interpolation)       // interpolation(1B)
        data.appendFloat32BE(videoRatio)     // video_ratio(4B)
        data.appendUInt8(mapStyle)           // map_style(1B)
        data.appendUInt8(showTrajectory ? 1 : 0)  // show_trajectory(1B)
        data.appendUInt8(showPoi ? 1 : 0)    // show_poi(1B)
        data.appendUInt8(defaultView)        // default_view(1B)
        return data
    }

    /// 从二进制解码
    public static func decode(data: Data, offset: Int) -> SyncRules? {
        guard offset + 14 <= data.count else { return nil }
        return SyncRules(
            syncMode: data[offset],
            syncOffsetMs: Int(data.readInt32BE(at: offset + 1)),
            interpolation: data[offset + 5],
            defaultView: data[offset + 13],
            videoRatio: data.readFloat32BE(at: offset + 6),
            mapStyle: data[offset + 10],
            showTrajectory: data[offset + 11] != 0,
            showPoi: data[offset + 12] != 0
        )
    }
}

/// gsyn payload 大小
public let GSYN_PAYLOAD_SIZE = 14
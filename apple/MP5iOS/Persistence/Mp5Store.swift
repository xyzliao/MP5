//
// Mp5Store.swift
// MP5iOS
//
// MP5 文件管理 — 使用 SwiftData 持久化文件记录
//
// 对应 Android版 Room数据库 和 Windows版 文件系统管理。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import Foundation
import SwiftData

/// MP5文件记录 — 存储在SwiftData数据库中
@Model
public final class Mp5FileRecord {
    public var filePath: String
    public var fileName: String
    public var fileSize: Int64
    public var durationMs: Int64
    public var createdAt: Date
    public var thumbnailPath: String?
    public var startLat: Double
    public var startLon: Double
    public var endLat: Double
    public var endLon: Double
    public var totalDistanceKm: Double
    public var maxSpeedKmh: Double
    public var gpsPointCount: Int
    public var hasMapData: Bool

    public init(
        filePath: String,
        fileName: String,
        fileSize: Int64,
        durationMs: Int64,
        createdAt: Date = Date(),
        thumbnailPath: String? = nil,
        startLat: Double = 0,
        startLon: Double = 0,
        endLat: Double = 0,
        endLon: Double = 0,
        totalDistanceKm: Double = 0,
        maxSpeedKmh: Double = 0,
        gpsPointCount: Int = 0,
        hasMapData: Bool = false
    ) {
        self.filePath = filePath
        self.fileName = fileName
        self.fileSize = fileSize
        self.durationMs = durationMs
        self.createdAt = createdAt
        self.thumbnailPath = thumbnailPath
        self.startLat = startLat
        self.startLon = startLon
        self.endLat = endLat
        self.endLon = endLon
        self.totalDistanceKm = totalDistanceKm
        self.maxSpeedKmh = maxSpeedKmh
        self.gpsPointCount = gpsPointCount
        self.hasMapData = hasMapData
    }
}

/// MP5 文件存储管理器
public class Mp5Store {

    /// 获取 App Documents 目录下的 mp5 子目录
    public static var mp5Directory: URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let dir = docs.appendingPathComponent("mp5", isDirectory: true)
        if !FileManager.default.fileExists(atPath: dir.path) {
            try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        return dir
    }

    /// 生成新的 MP5 文件 URL
    public static func newMp5FileUrl() -> URL {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        let timestamp = formatter.string(from: Date())
        return mp5Directory.appendingPathComponent("MP5_\(timestamp).mp5")
    }

    /// 生成临时 MP4 文件 URL
    public static func newTempMp4FileUrl() -> URL {
        let tempDir = FileManager.default.temporaryDirectory
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd_HHmmss"
        let timestamp = formatter.string(from: Date())
        return tempDir.appendingPathComponent("temp_\(timestamp).mp4")
    }

    /// 删除文件
    public static func deleteFile(at path: String) {
        let url = URL(fileURLWithPath: path)
        try? FileManager.default.removeItem(at: url)
    }
}
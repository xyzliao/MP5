//
// FileListViewModel.swift
// MP5macOS
//
// 文件列表ViewModel — 管理MP5文件列表数据
//
// 与 iOS版 FileListViewModel 逻辑一致，适配 macOS SwiftData。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation
import SwiftData
import SwiftUI
import MP5Core

@MainActor
public class FileListViewModel: ObservableObject {

    @Published public var files: [Mp5FileRecord] = []
    @Published public var isLoading = false

    private var modelContext: ModelContext?

    public func configure(context: ModelContext) {
        self.modelContext = context
        loadFiles()
    }

    /// 加载文件列表
    public func loadFiles() {
        guard let context = modelContext else { return }
        let descriptor = FetchDescriptor<Mp5FileRecord>(
            sortBy: [SortDescriptor(\.createdAt, order: .reverse)]
        )
        do {
            files = try context.fetch(descriptor)
        } catch {
            print("加载文件列表失败: \(error)")
            files = []
        }
    }

    /// 删除文件
    public func deleteFile(_ file: Mp5FileRecord) {
        guard let context = modelContext else { return }
        Mp5Store.deleteFile(at: file.filePath)
        context.delete(file)
        try? context.save()
        loadFiles()
    }

    /// 添加新文件记录
    public func addFileRecord(
        filePath: String,
        fileName: String,
        fileSize: Int64,
        durationMs: Int64,
        startLat: Double,
        startLon: Double,
        endLat: Double,
        endLon: Double,
        totalDistanceKm: Double,
        maxSpeedKmh: Double,
        gpsPointCount: Int
    ) {
        guard let context = modelContext else { return }
        let record = Mp5FileRecord(
            filePath: filePath,
            fileName: fileName,
            fileSize: fileSize,
            durationMs: durationMs,
            startLat: startLat,
            startLon: startLon,
            endLat: endLat,
            endLon: endLon,
            totalDistanceKm: totalDistanceKm,
            maxSpeedKmh: maxSpeedKmh,
            gpsPointCount: gpsPointCount
        )
        context.insert(record)
        try? context.save()
        loadFiles()
    }

    /// 扫描 mp5 目录，将未入库的文件加入数据库
    public func scanMp5Directory() {
        guard let context = modelContext else { return }
        let dir = Mp5Store.mp5Directory
        guard let fileURLs = try? FileManager.default.contentsOfDirectory(
            at: dir, includingPropertiesForKeys: [.fileSizeKey, .creationDateKey]
        ) else { return }

        for url in fileURLs where url.pathExtension == "mp5" {
            let path = url.path
            // 检查是否已存在
            let existing = files.first { $0.filePath == path }
            if existing != nil { continue }

            // 解析MP5获取元数据
            guard let data = try? Data(contentsOf: url) else { continue }
            let info = Mp5Parser.parse(data)

            let attrs = try? url.resourceValues(forKeys: [.fileSizeKey, .creationDateKey])
            let fileSize = Int64(attrs?.fileSize ?? data.count)
            let createdAt = attrs?.creationDate ?? Date()

            let record = Mp5FileRecord(
                filePath: path,
                fileName: url.lastPathComponent,
                fileSize: fileSize,
                durationMs: Int64(info.durationMs),
                createdAt: createdAt,
                startLat: info.gpsSamples.first?.latitude ?? 0,
                startLon: info.gpsSamples.first?.longitude ?? 0,
                endLat: info.gpsSamples.last?.latitude ?? 0,
                endLon: info.gpsSamples.last?.longitude ?? 0,
                totalDistanceKm: Mp5Parser.getTotalDistance(samples: info.gpsSamples),
                maxSpeedKmh: Mp5Parser.getMaxSpeed(samples: info.gpsSamples),
                gpsPointCount: info.gpsSamples.count,
                hasMapData: info.hasMapData
            )
            context.insert(record)
        }
        try? context.save()
        loadFiles()
    }
}
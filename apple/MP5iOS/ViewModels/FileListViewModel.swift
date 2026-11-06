//
// FileListViewModel.swift
// MP5iOS
//
// 文件列表ViewModel — 管理MP5文件列表数据
//
// 对应 Android版 FileListScreen 中的数据逻辑。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation
import SwiftData
import SwiftUI

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
}
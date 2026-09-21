//
// FileListView.swift
// MP5macOS
//
// 文件列表界面 — macOS侧边栏样式的MP5文件列表
//
// 对应 iOS版 FileListView，适配 macOS NavigationSplitView 侧边栏。
// 支持：文件列表、删除、扫描目录、创建MP5。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import SwiftUI
import SwiftData
import MP5Core

struct FileListView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel = FileListViewModel()
    @Query(sort: \Mp5FileRecord.createdAt, order: .reverse) private var files: [Mp5FileRecord]
    @Binding var selectedFile: Mp5FileRecord?
    @State private var showCreateMp5 = false

    var body: some View {
        VStack(spacing: 0) {
            // 顶部工具栏
            HStack {
                Text("MP5文件")
                    .font(.headline)
                Spacer()
                Button {
                    showCreateMp5 = true
                } label: {
                    Image(systemName: "plus.circle")
                }
                .help("从MP4制作MP5")
                Button {
                    viewModel.scanMp5Directory()
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .help("扫描MP5目录")
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)

            Divider()

            // 文件列表
            if files.isEmpty {
                emptyState
            } else {
                fileList
            }
        }
        .frame(minWidth: 260, idealWidth: 300, maxWidth: 400)
        .sheet(isPresented: $showCreateMp5) {
            CreateMp5View()
        }
        .onAppear {
            viewModel.configure(context: modelContext)
            viewModel.scanMp5Directory()
        }
    }

    // 空状态
    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "video.slash")
                .font(.system(size: 40))
                .foregroundStyle(.secondary)
            Text("还没有MP5文件")
                .font(.body)
                .foregroundStyle(.secondary)
            Text("点击 + 从MP4制作MP5")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // 文件列表
    private var fileList: some View {
        List(selection: $selectedFile) {
            ForEach(files) { file in
                FileCardView(file: file)
                    .tag(file)
                    .contextMenu {
                        Button("删除", role: .destructive) {
                            if selectedFile == file {
                                selectedFile = nil
                            }
                            viewModel.deleteFile(file)
                        }
                        Divider()
                        Button("在Finder中显示") {
                            NSWorkspace.shared.selectFile(file.filePath, inFileViewerRootedAtPath: "")
                        }
                    }
            }
        }
        .listStyle(.sidebar)
    }
}

/// 文件卡片（macOS样式）
struct FileCardView: View {
    let file: Mp5FileRecord

    private var durationText: String {
        let totalSec = file.durationMs / 1000
        let h = totalSec / 3600
        let m = (totalSec % 3600) / 60
        let s = totalSec % 60
        return h > 0 ? "\(h):\(String(format: "%02d", m)):\(String(format: "%02d", s))"
                     : "\(String(format: "%02d", m)):\(String(format: "%02d", s))"
    }

    private var sizeText: String {
        if file.fileSize >= 1_000_000_000 {
            return String(format: "%.1fGB", Double(file.fileSize) / 1_000_000_000)
        } else if file.fileSize >= 1_000_000 {
            return String(format: "%.1fMB", Double(file.fileSize) / 1_000_000)
        } else if file.fileSize >= 1_000 {
            return String(format: "%.0fKB", Double(file.fileSize) / 1_000)
        }
        return "\(file.fileSize)B"
    }

    private var dateText: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MM-dd HH:mm"
        return formatter.string(from: file.createdAt)
    }

    var body: some View {
        HStack(spacing: 10) {
            // 图标
            ZStack {
                RoundedRectangle(cornerRadius: 6)
                    .fill(Color.red.opacity(0.15))
                    .frame(width: 36, height: 36)
                Image(systemName: "play.fill")
                    .foregroundStyle(.red)
                    .font(.system(size: 14))
            }

            // 信息
            VStack(alignment: .leading, spacing: 2) {
                Text(file.fileName)
                    .font(.body)
                    .lineLimit(1)

                HStack(spacing: 8) {
                    Text(durationText)
                    Text(sizeText)
                    if file.gpsPointCount > 0 {
                        HStack(spacing: 2) {
                            Image(systemName: "location.fill")
                                .font(.caption2)
                            Text("\(file.gpsPointCount)点")
                        }
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                if file.startLat != 0 {
                    Text(String(format: "%.4f°N %.4f°E", file.startLat, file.startLon))
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }

                Text(dateText)
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }

            Spacer()
        }
        .padding(.vertical, 4)
    }
}
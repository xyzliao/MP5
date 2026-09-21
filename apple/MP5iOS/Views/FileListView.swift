//
// FileListView.swift
// MP5iOS
//
// 文件列表界面 — 显示所有MP5录制文件
//
// 对应 Android版 FileListScreen。
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
    @State private var selectedFile: Mp5FileRecord?
    @State private var showCreateMp5 = false

    var body: some View {
        NavigationStack {
            Group {
                if files.isEmpty {
                    emptyState
                } else {
                    fileList
                }
            }
            .navigationTitle("MP5录播器")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showCreateMp5 = true
                    } label: {
                        Image(systemName: "plus.circle")
                    }
                }
            }
            .sheet(item: $selectedFile) { file in
                PlaybackView(filePath: file.filePath)
            }
            .sheet(isPresented: $showCreateMp5) {
                CreateMp5View()
            }
        }
        .onAppear {
            viewModel.configure(context: modelContext)
        }
    }

    // 空状态
    private var emptyState: some View {
        VStack(spacing: 16) {
            Image(systemName: "video.slash")
                .font(.system(size: 60))
                .foregroundStyle(.secondary)

            Text("还没有MP5文件")
                .font(.title2)
                .foregroundStyle(.secondary)

            Text("切换到\"录制\"标签开始录制\n或点击右上角从MP4制作MP5")
                .font(.body)
                .foregroundStyle(.tertiary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // 文件列表
    private var fileList: some View {
        List {
            ForEach(files) { file in
                FileCardView(file: file)
                    .contentShape(Rectangle())
                    .onTapGesture {
                        selectedFile = file
                    }
                    .swipeActions(edge: .trailing) {
                        Button(role: .destructive) {
                            viewModel.deleteFile(file)
                        } label: {
                            Label("删除", systemImage: "trash")
                        }
                    }
            }
        }
        .listStyle(.plain)
    }
}

/// 文件卡片
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
        HStack(spacing: 12) {
            // 图标
            ZStack {
                Circle()
                    .fill(Color.red.opacity(0.2))
                    .frame(width: 44, height: 44)
                Image(systemName: "play.fill")
                    .foregroundStyle(.red)
            }

            // 信息
            VStack(alignment: .leading, spacing: 4) {
                Text(file.fileName)
                    .font(.body)
                    .lineLimit(1)

                HStack(spacing: 12) {
                    Text(durationText)
                    Text(sizeText)
                    if file.gpsPointCount > 0 {
                        HStack(spacing: 2) {
                            Image(systemName: "location.fill")
                                .font(.caption)
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
//
// MP5MacApp.swift
// MP5macOS
//
// MP5录播器 — macOS版应用入口
//
// 功能：
//   - MP5文件播放（视频+地图双窗口联动，大屏体验）
//   - 从MP4制作MP5（导入GPX）
//   - 导出 GPX / GeoJSON / KML / MP4
//   - 不含录制（macOS无摄像头/GPS采集需求）
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import SwiftUI
import SwiftData

@main
struct MP5MacApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .frame(minWidth: 900, minHeight: 600)
        }
        .modelContainer(for: Mp5FileRecord.self)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("从MP4制作MP5...") {
                    NotificationCenter.default.post(name: .createMp5Menu, object: nil)
                }
                .keyboardShortcut("n", modifiers: .command)
            }
        }
    }
}

/// 主内容视图 — macOS侧边栏导航
struct ContentView: View {
    @State private var selectedFile: Mp5FileRecord?
    @State private var showCreateMp5 = false

    var body: some View {
        NavigationSplitView {
            // 侧边栏：文件列表
            FileListView(selectedFile: $selectedFile)
        } detail: {
            // 主区域：播放界面
            if let file = selectedFile {
                PlaybackView(filePath: file.filePath)
            } else {
                // 空状态
                VStack(spacing: 20) {
                    Image(systemName: "video.square.fill")
                        .font(.system(size: 80))
                        .foregroundStyle(.red.opacity(0.6))

                    Text("MP5录播器")
                        .font(.largeTitle)
                        .fontWeight(.bold)

                    Text("选择左侧文件开始播放\n或从菜单「文件 → 从MP4制作MP5」创建新文件")
                        .font(.body)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)

                    Text("版本 1.0.21  ·  大米斗（Aniseedaliao）")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color(NSColor.windowBackgroundColor))
            }
        }
        .sheet(isPresented: $showCreateMp5) {
            CreateMp5View()
        }
        .onReceive(NotificationCenter.default.publisher(for: .createMp5Menu)) { _ in
            showCreateMp5 = true
        }
    }
}

// 通知名称扩展
extension Notification.Name {
    static let createMp5Menu = Notification.Name("createMp5Menu")
}
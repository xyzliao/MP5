//
// MP5iOSApp.swift
// MP5iOS
//
// MP5录播器 — iOS版应用入口
//
// 功能：
//   - MP5文件录制（视频+GPS同步采集）
//   - MP5文件播放（视频+地图双窗口联动）
//   - 导出 GPX / GeoJSON / KML / MP4
//   - 从MP4制作MP5（导入GPX）
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import SwiftUI
import SwiftData

@main
struct MP5iOSApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: Mp5FileRecord.self)
    }
}

/// 主内容视图 — Tab导航
struct ContentView: View {
    var body: some View {
        TabView {
            FileListView()
                .tabItem {
                    Label("文件", systemImage: "folder")
                }

            RecordView()
                .tabItem {
                    Label("录制", systemImage: "video.fill")
                }
        }
        .tint(.red)
    }
}
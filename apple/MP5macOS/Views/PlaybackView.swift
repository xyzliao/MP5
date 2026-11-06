//
// PlaybackView.swift
// MP5macOS
//
// 播放界面 — 视频播放 + GPS地图同步（macOS大屏版）
//
// 对应 iOS版 PlaybackView，适配 macOS 大屏体验：
//   - 使用 HSplitView / VSplitView 原生分屏（可拖拽调整比例）
//   - 5种视图模式：仅视频、仅地图、左右分屏、上下分屏、画中画
//   - 导出菜单（GPX / GeoJSON / KML / MP4）
//   - 键盘快捷键（空格暂停/播放，左右箭头快进/快退）
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import SwiftUI
import AVKit
import MapKit
import AppKit
import MP5Core

struct PlaybackView: View {
    let filePath: String
    @StateObject private var viewModel = PlaybackViewModel()
    @State private var showExportMenu = false

    var body: some View {
        VStack(spacing: 0) {
            // 顶部工具栏
            topBar

            // 主内容区
            contentArea

            // 底部控制栏
            controlBar
        }
        .background(Color.black)
        .onAppear {
            let url = URL(fileURLWithPath: filePath)
            viewModel.loadFile(url)
        }
        .onDisappear {
            viewModel.release()
        }
        // 键盘快捷键
        .onKeyPress(.space) {
            if viewModel.isPlaying {
                viewModel.pause()
            } else {
                viewModel.play()
            }
            return .handled
        }
        .onKeyPress(.leftArrow) {
            viewModel.seekTo(ms: max(0, viewModel.currentPositionMs - 10_000))
            return .handled
        }
        .onKeyPress(.rightArrow) {
            viewModel.seekTo(ms: min(viewModel.durationMs, viewModel.currentPositionMs + 10_000))
            return .handled
        }
    }

    // 顶部工具栏
    private var topBar: some View {
        HStack {
            Text(viewModel.isMp5 ? "MP5播放" : "MP4播放")
                .font(.headline)
                .foregroundStyle(.white)

            Spacer()

            // 视图切换按钮组
            HStack(spacing: 16) {
                viewModeButton(.videoOnly, icon: "video.fill", label: "仅视频")
                viewModeButton(.mapOnly, icon: "map.fill", label: "仅地图")
                viewModeButton(.splitLR, icon: "rectangle.split.2x1", label: "左右分屏")
                viewModeButton(.splitTB, icon: "rectangle.split.2x1.slash", label: "上下分屏")
                viewModeButton(.pip, icon: "pip.fill", label: "画中画")
            }

            Spacer()

            // 导出按钮
            Menu {
                Button("导出 GPX...") { exportGpx() }
                Button("导出 GeoJSON...") { exportGeoJson() }
                Button("导出 KML...") { exportKml() }
                Divider()
                Button("导出 MP4（剥离GPS）...") { exportMp4() }
            } label: {
                Label("导出", systemImage: "square.and.arrow.up")
                    .labelStyle(.iconOnly)
            }
            .menuStyle(.borderlessButton)
            .foregroundStyle(.white)
            .disabled(!viewModel.isMp5)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.9))
    }

    private func viewModeButton(_ mode: ViewMode, icon: String, label: String) -> some View {
        Button {
            viewModel.viewMode = mode
        } label: {
            Image(systemName: icon)
                .foregroundStyle(viewModel.viewMode == mode ? .red : .white)
                .font(.body)
        }
        .help(label)
        .buttonStyle(.plain)
    }

    // 主内容区 — macOS 使用 HSplitView / VSplitView 支持拖拽调整
    @ViewBuilder
    private var contentArea: some View {
        switch viewModel.viewMode {
        case .videoOnly:
            VideoPlayerView(viewModel: viewModel)
                .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .mapOnly:
            Mp5MapView(
                gpsSamples: viewModel.gpsSamples,
                currentGps: viewModel.currentGps,
                onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
            )
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .splitLR:
            HSplitView {
                VideoPlayerView(viewModel: viewModel)
                    .frame(minWidth: 300, minHeight: 200)
                Mp5MapView(
                    gpsSamples: viewModel.gpsSamples,
                    currentGps: viewModel.currentGps,
                    onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
                )
                .frame(minWidth: 300, minHeight: 200)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .splitTB:
            VSplitView {
                VideoPlayerView(viewModel: viewModel)
                    .frame(minWidth: 300, minHeight: 150)
                Mp5MapView(
                    gpsSamples: viewModel.gpsSamples,
                    currentGps: viewModel.currentGps,
                    onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
                )
                .frame(minWidth: 300, minHeight: 150)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .pip:
            ZStack {
                VideoPlayerView(viewModel: viewModel)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                Mp5MapView(
                    gpsSamples: viewModel.gpsSamples,
                    currentGps: viewModel.currentGps,
                    onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
                )
                .frame(width: 320, height: 240)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .overlay(
                    RoundedRectangle(cornerRadius: 10)
                        .stroke(.white.opacity(0.3), lineWidth: 1)
                )
                .padding(12)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
            }
        }
    }

    // 底部控制栏
    private var controlBar: some View {
        VStack(spacing: 6) {
            // 进度条
            if viewModel.durationMs > 0 {
                HStack {
                    Text(formatTime(viewModel.currentPositionMs))
                        .font(.caption)
                        .foregroundStyle(.white)
                        .monospacedDigit()

                    Slider(
                        value: Binding(
                            get: { Double(viewModel.currentPositionMs) },
                            set: { viewModel.seekTo(ms: Int64($0)) }
                        ),
                        in: 0...Double(viewModel.durationMs)
                    )
                    .tint(.red)

                    Text(formatTime(viewModel.durationMs))
                        .font(.caption)
                        .foregroundStyle(.white)
                        .monospacedDigit()
                }
                .padding(.horizontal, 16)
            }

            // 播放控制
            HStack(spacing: 40) {
                Button {
                    viewModel.seekTo(ms: max(0, viewModel.currentPositionMs - 10_000))
                } label: {
                    Image(systemName: "gobackward.10")
                        .font(.title3)
                        .foregroundStyle(.white)
                }
                .buttonStyle(.plain)
                .keyboardShortcut(.leftArrow, modifiers: [])

                Button {
                    if viewModel.isPlaying {
                        viewModel.pause()
                    } else {
                        viewModel.play()
                    }
                } label: {
                    Image(systemName: viewModel.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(.red)
                }
                .buttonStyle(.plain)

                Button {
                    viewModel.seekTo(ms: min(viewModel.durationMs, viewModel.currentPositionMs + 10_000))
                } label: {
                    Image(systemName: "goforward.10")
                        .font(.title3)
                        .foregroundStyle(.white)
                }
                .buttonStyle(.plain)
                .keyboardShortcut(.rightArrow, modifiers: [])
            }

            // GPS信息
            if let gps = viewModel.currentGps {
                HStack {
                    Text(String(format: "%.4f°N %.4f°E", gps.0, gps.1))
                    if viewModel.totalDistance > 0 {
                        Spacer()
                        Text(String(format: "%.1fkm  最大%.0fkm/h", viewModel.totalDistance, viewModel.maxSpeed))
                    }
                }
                .font(.caption)
                .foregroundStyle(.white.opacity(0.7))
                .padding(.horizontal, 16)
                .padding(.bottom, 4)
            }
        }
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.9))
    }

    private func formatTime(_ ms: Int64) -> String {
        if ms <= 0 { return "00:00" }
        let totalSec = ms / 1000
        let m = (totalSec % 3600) / 60
        let s = totalSec % 60
        let h = totalSec / 3600
        return h > 0 ? "\(h):\(String(format: "%02d", m)):\(String(format: "%02d", s))"
                     : "\(String(format: "%02d", m)):\(String(format: "%02d", s))"
    }

    // MARK: - 导出

    private func exportGpx() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.xml]
        panel.nameFieldStringValue = "track.gpx"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        try? viewModel.exportGpx(to: url)
    }

    private func exportGeoJson() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.json]
        panel.nameFieldStringValue = "track.geojson"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        try? viewModel.exportGeoJson(to: url)
    }

    private func exportKml() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.xml]
        panel.nameFieldStringValue = "track.kml"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        try? viewModel.exportKml(to: url)
    }

    private func exportMp4() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.mpeg4Movie]
        panel.nameFieldStringValue = "video.mp4"
        guard panel.runModal() == .OK, let url = panel.url else { return }

        // 从原始文件读取数据并导出
        let srcUrl = URL(fileURLWithPath: filePath)
        guard let data = try? Data(contentsOf: srcUrl) else { return }
        let mp4Data = Mp4Exporter.extractMp4(from: data)
        try? mp4Data.write(to: url)
    }
}

/// AVPlayer 视频播放视图
struct VideoPlayerView: View {
    @ObservedObject var viewModel: PlaybackViewModel

    var body: some View {
        if let player = viewModel.player {
            VideoPlayer(player: player)
                .ignoresSafeArea()
        } else {
            Color.black
                .overlay(
                    ProgressView()
                        .tint(.white)
                )
        }
    }
}
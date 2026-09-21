//
// PlaybackView.swift
// MP5iOS
//
// 播放界面 — 视频播放 + GPS地图同步
//
// 对应 Android版 PlaybackScreen。
// 使用 AVPlayer 视频播放 + MapKit 地图渲染，5种视图模式。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import SwiftUI
import AVKit
import MapKit
import MP5Core

struct PlaybackView: View {
    let filePath: String
    @StateObject private var viewModel = PlaybackViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                VStack(spacing: 0) {
                    // 顶部栏
                    topBar

                    // 主内容区
                    contentArea

                    // 底部控制栏
                    controlBar
                }
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        viewModel.release()
                        dismiss()
                    } label: {
                        Image(systemName: "chevron.left")
                            .foregroundStyle(.white)
                    }
                }
            }
            .toolbarBackground(.black, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .onAppear {
            let url = URL(fileURLWithPath: filePath)
            viewModel.loadFile(url)
        }
        .onDisappear {
            viewModel.release()
        }
    }

    // 顶部栏
    private var topBar: some View {
        HStack {
            Text(viewModel.isMp5 ? "MP5播放" : "MP4播放")
                .font(.headline)
                .foregroundStyle(.white)

            Spacer()

            // 视图切换按钮
            HStack(spacing: 12) {
                viewModeButton(.videoOnly, icon: "video.fill")
                viewModeButton(.mapOnly, icon: "map.fill")
                viewModeButton(.splitLR, icon: "rectangle.split.2x1")
                viewModeButton(.pip, icon: "pip.fill")
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.8))
    }

    private func viewModeButton(_ mode: ViewMode, icon: String) -> some View {
        Button {
            viewModel.viewMode = mode
        } label: {
            Image(systemName: icon)
                .foregroundStyle(viewModel.viewMode == mode ? .red : .white)
                .font(.body)
        }
    }

    // 主内容区
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
            HStack(spacing: 0) {
                VideoPlayerView(viewModel: viewModel)
                Mp5MapView(
                    gpsSamples: viewModel.gpsSamples,
                    currentGps: viewModel.currentGps,
                    onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
                )
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

        case .splitTB:
            VStack(spacing: 0) {
                VideoPlayerView(viewModel: viewModel)
                Mp5MapView(
                    gpsSamples: viewModel.gpsSamples,
                    currentGps: viewModel.currentGps,
                    onMapClick: { lat, lon in viewModel.seekToGps(lat: lat, lon: lon) }
                )
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
                .frame(width: 160, height: 120)
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(.white.opacity(0.3), lineWidth: 1)
                )
                .padding(8)
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomTrailing)
            }
        }
    }

    // 底部控制栏
    private var controlBar: some View {
        VStack(spacing: 8) {
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
                .padding(.horizontal)
            }

            // 播放控制
            HStack(spacing: 30) {
                Button {
                    viewModel.seekTo(ms: max(0, viewModel.currentPositionMs - 10_000))
                } label: {
                    Image(systemName: "gobackward.10")
                        .font(.title2)
                        .foregroundStyle(.white)
                }

                Button {
                    if viewModel.isPlaying {
                        viewModel.pause()
                    } else {
                        viewModel.play()
                    }
                } label: {
                    Image(systemName: viewModel.isPlaying ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 44))
                        .foregroundStyle(.red)
                }

                Button {
                    viewModel.seekTo(ms: min(viewModel.durationMs, viewModel.currentPositionMs + 10_000))
                } label: {
                    Image(systemName: "goforward.10")
                        .font(.title2)
                        .foregroundStyle(.white)
                }
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
                .padding(.horizontal)
                .padding(.bottom, 4)
            }
        }
        .padding(.vertical, 8)
        .background(Color.black.opacity(0.8))
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
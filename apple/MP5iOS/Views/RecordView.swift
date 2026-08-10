//
// RecordView.swift
// MP5iOS
//
// 录制界面 — AVFoundation视频预览 + GPS采集 + 录制控制
//
// 对应 Android版 RecordScreen。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import SwiftUI
import AVFoundation
import MP5Core

struct RecordView: View {
    @Environment(\.modelContext) private var modelContext
    @StateObject private var viewModel = RecordViewModel()
    @State private var showPoiLabel = false
    @State private var poiLabel = ""

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 0) {
                // 视频预览区域
                ZStack {
                    // 摄像头预览
                    if viewModel.state == .idle {
                        Text("点击录制按钮开始")
                            .foregroundStyle(.white.opacity(0.5))
                    } else {
                        CameraPreviewLayerView(recorder: viewModel.recorder)
                    }

                    // 顶部状态栏
                    if viewModel.state == .recording || viewModel.state == .paused {
                        VStack {
                            HStack {
                                if viewModel.state == .recording {
                                    HStack(spacing: 4) {
                                        Circle()
                                            .fill(.red)
                                            .frame(width: 8, height: 8)
                                        Text(formatTime(viewModel.elapsedMs))
                                            .font(.subheadline.bold())
                                            .foregroundStyle(.white)
                                    }
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 6)
                                    .background(.black.opacity(0.5))
                                    .clipShape(Capsule())
                                }

                                Spacer()

                                // GPS状态
                                HStack(spacing: 4) {
                                    Image(systemName: "location.fill")
                                        .foregroundStyle(viewModel.currentLocation != nil ? .green : .gray)
                                        .font(.caption)
                                    Text("\(viewModel.gpsSampleCount)")
                                        .font(.caption)
                                        .foregroundStyle(.white)
                                }
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(.black.opacity(0.5))
                                .clipShape(Capsule())
                            }
                            .padding()

                            Spacer()

                            // 底部GPS信息
                            if let loc = viewModel.currentLocation {
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(String(format: "%.4f°N %.4f°E", loc.latitude, loc.longitude))
                                        Text(String(format: "%.0f km/h  %.0fm", loc.speedKmh, loc.altitudeM))
                                    }
                                    .font(.caption)
                                    .foregroundStyle(.white)
                                    .padding(8)
                                    .background(.black.opacity(0.5))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                                    .padding()
                                }
                            }
                        }
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                // 控制栏
                controlBar
            }
        }
        .onAppear {
            viewModel.requestPermissions()
        }
        .onDisappear {
            if viewModel.state == .recording || viewModel.state == .paused {
                viewModel.stop()
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .mp5RecordingCompleted)) { notification in
            viewModel.handleRecordingCompleted(notification: notification, context: modelContext)
        }
        .alert("标记POI", isPresented: $showPoiLabel) {
            TextField("标签（可选）", text: $poiLabel)
            Button("标记") {
                viewModel.addPoi(label: poiLabel.isEmpty ? nil : poiLabel)
                poiLabel = ""
            }
            Button("取消", role: .cancel) {
                poiLabel = ""
            }
        }
    }

    // 控制栏
    @ViewBuilder
    private var controlBar: some View {
        HStack(spacing: 40) {
            switch viewModel.state {
            case .idle:
                // 录制按钮
                Button {
                    viewModel.start()
                } label: {
                    ZStack {
                        Circle()
                            .stroke(.white, lineWidth: 3)
                            .frame(width: 70, height: 70)
                        Circle()
                            .fill(.red)
                            .frame(width: 56, height: 56)
                    }
                }

            case .recording:
                // 暂停
                Button {
                    viewModel.pause()
                } label: {
                    Image(systemName: "pause.fill")
                        .font(.title)
                        .foregroundStyle(.white)
                        .frame(width: 56, height: 56)
                        .background(.white.opacity(0.2))
                        .clipShape(Circle())
                }

                // POI标记
                Button {
                    showPoiLabel = true
                } label: {
                    Image(systemName: "mappin.circle.fill")
                        .font(.title)
                        .foregroundStyle(.yellow)
                        .frame(width: 56, height: 56)
                        .background(.white.opacity(0.2))
                        .clipShape(Circle())
                }

                // 停止
                Button {
                    viewModel.stop()
                } label: {
                    ZStack {
                        Circle()
                            .stroke(.white, lineWidth: 3)
                            .frame(width: 70, height: 70)
                        RoundedRectangle(cornerRadius: 6)
                            .fill(.red)
                            .frame(width: 28, height: 28)
                    }
                }

            case .paused:
                // 继续
                Button {
                    viewModel.resume()
                } label: {
                    Image(systemName: "play.fill")
                        .font(.title)
                        .foregroundStyle(.white)
                        .frame(width: 56, height: 56)
                        .background(.white.opacity(0.2))
                        .clipShape(Circle())
                }

                // 停止
                Button {
                    viewModel.stop()
                } label: {
                    ZStack {
                        Circle()
                            .stroke(.white, lineWidth: 3)
                            .frame(width: 70, height: 70)
                        RoundedRectangle(cornerRadius: 6)
                            .fill(.red)
                            .frame(width: 28, height: 28)
                    }
                }

            case .finalizing:
                VStack(spacing: 8) {
                    ProgressView()
                        .tint(.white)
                    Text("正在封装MP5...")
                        .font(.caption)
                        .foregroundStyle(.white)
                }
            }
        }
        .frame(height: 100)
        .frame(maxWidth: .infinity)
        .background(Color.black)
    }

    private func formatTime(_ ms: Int64) -> String {
        let totalSec = ms / 1000
        let h = totalSec / 3600
        let m = (totalSec % 3600) / 60
        let s = totalSec % 60
        return h > 0 ? "\(h):\(String(format: "%02d", m)):\(String(format: "%02d", s))"
                     : "\(String(format: "%02d", m)):\(String(format: "%02d", s))"
    }
}

/// 摄像头预览图层
struct CameraPreviewLayerView: UIViewRepresentable {
    let recorder: Mp5Recorder

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = recorder.videoRecorder.session
        view.previewLayer.videoGravity = .resizeAspectFill
        recorder.videoRecorder.startSession()
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}
}

/// 预览视图
class PreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer {
        layer as! AVCaptureVideoPreviewLayer
    }
}
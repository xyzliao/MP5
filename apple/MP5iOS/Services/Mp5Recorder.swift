//
// Mp5Recorder.swift
// MP5iOS
//
// MP5录制器 — 协调视频录制 + GPS采集 + MP5封装
//
// 流程：
// 1. 启动AVFoundation录制MP4到临时文件
// 2. 同时启动GPS采集
// 3. 停止后：用Mp5Muxer将gloc/gpoi/gsyn box嵌入MP4 → MP5
// 4. 在SwiftData数据库中登记文件
//
// 对应 Android版 Mp5Recorder。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import Foundation
import AVFoundation
import SwiftUI
import SwiftData
import MP5Core

/// MP5录制器状态
public enum RecorderState: Equatable {
    case idle
    case recording
    case paused
    case finalizing
}

/// MP5录制器 — 协调视频录制 + GPS采集 + MP5封装
@MainActor
public class Mp5Recorder: ObservableObject {

    @Published public var state: RecorderState = .idle
    @Published public var elapsedMs: Int64 = 0
    @Published public var currentLocation: GpsSample?
    @Published public var gpsSampleCount: Int = 0

    public let videoRecorder = VideoRecorder()
    private let gpsCollector = GpsCollector()
    private var startTimeMs: Int64 = 0
    private var tempMp4Url: URL?
    private var pendingGpsSamples: [GpsSample] = []
    private var timer: Timer?

    public var lastInsertedId: UUID?

    public init() {
        // 绑定GPS回调
        gpsCollector.onLocationUpdate = { [weak self] sample in
            DispatchQueue.main.async {
                self?.currentLocation = sample
            }
        }
        gpsCollector.onSampleCountChange = { [weak self] count in
            DispatchQueue.main.async {
                self?.gpsSampleCount = count
            }
        }
    }

    /// 请求权限
    public func requestPermissions() {
        gpsCollector.requestPermission()
        // 摄像头权限由 AVCaptureDevice.requestAccess 处理
        AVCaptureDevice.requestAccess(for: .video) { _ in }
    }

    /// 开始录制
    public func start() {
        guard state == .idle else { return }

        do {
            try videoRecorder.configure()
        } catch {
            print("摄像头配置失败: \(error)")
            return
        }

        startTimeMs = Int64(Date().timeIntervalSince1970 * 1000)
        elapsedMs = 0

        // 创建临时MP4文件
        let tempUrl = Mp5Store.newTempMp4FileUrl()
        tempMp4Url = tempUrl

        // 启动GPS采集
        gpsCollector.start(sampleRateHz: 1, startTimeMs: startTimeMs)

        // 启动视频录制
        videoRecorder.onRecordingFinished = { [weak self] url in
            self?.finalizeMp5()
        }
        videoRecorder.onRecordingError = { [weak self] error in
            print("录制错误: \(error)")
            self?.state = .idle
        }
        videoRecorder.startRecording(to: tempUrl)

        // 启动计时器
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.elapsedMs = Int64(Date().timeIntervalSince1970 * 1000) - self.startTimeMs
        }

        state = .recording
    }

    /// 暂停录制
    public func pause() {
        videoRecorder.pauseRecording()
        gpsCollector.pause()
        timer?.invalidate()
        state = .paused
    }

    /// 继续录制
    public func resume() {
        videoRecorder.resumeRecording()
        gpsCollector.resume()
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in
            guard let self = self else { return }
            self.elapsedMs = Int64(Date().timeIntervalSince1970 * 1000) - self.startTimeMs
        }
        state = .recording
    }

    /// 停止录制
    public func stop() {
        state = .finalizing
        timer?.invalidate()
        pendingGpsSamples = gpsCollector.stop()
        videoRecorder.stopRecording()
    }

    /// 添加POI标记
    public func addPoi(label: String? = nil) {
        gpsCollector.addPoi(label: label)
    }

    /// 封装MP5文件
    private func finalizeMp5() {
        guard let mp4Url = tempMp4Url else {
            state = .idle
            return
        }

        let mp5Url = Mp5Store.newMp5FileUrl()

        // 在后台线程执行封装
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let mp4Data = try Data(contentsOf: mp4Url)

                let muxer = Mp5Muxer()
                let poiSamples = self.pendingGpsSamples.filter { $0.isPoi }
                let pois = poiSamples.map { s in
                    Poi(timestampMs: s.timestampMs, latitude: s.latitude, longitude: s.longitude, label: s.poiLabel ?? "")
                }

                let mp5Data = muxer.mux(
                    mp4Data: mp4Data,
                    gpsSamples: self.pendingGpsSamples,
                    syncRules: SyncRules(),
                    pois: pois
                )

                try mp5Data.write(to: mp5Url)

                // 删除临时MP4
                try? FileManager.default.removeItem(at: mp4Url)

                // 计算统计信息
                let firstGps = self.pendingGpsSamples.first
                let lastGps = self.pendingGpsSamples.last
                let totalDistance = Mp5Parser.getTotalDistance(samples: self.pendingGpsSamples)
                let maxSpeed = Mp5Parser.getMaxSpeed(samples: self.pendingGpsSamples)

                // 回到主线程更新UI
                DispatchQueue.main.async {
                    // 保存到数据库由ViewModel处理
                    self.state = .idle
                    self.lastInsertedId = UUID()

                    // 发送完成通知
                    NotificationCenter.default.post(
                        name: .mp5RecordingCompleted,
                        object: nil,
                        userInfo: [
                            "filePath": mp5Url.path,
                            "fileName": mp5Url.lastPathComponent,
                            "fileSize": mp5Data.count,
                            "durationMs": self.elapsedMs,
                            "startLat": firstGps?.latitude ?? 0,
                            "startLon": firstGps?.longitude ?? 0,
                            "endLat": lastGps?.latitude ?? 0,
                            "endLon": lastGps?.longitude ?? 0,
                            "totalDistanceKm": totalDistance,
                            "maxSpeedKmh": maxSpeed,
                            "gpsPointCount": self.pendingGpsSamples.count
                        ]
                    )
                }
            } catch {
                DispatchQueue.main.async {
                    print("MP5封装失败: \(error)")
                    self.state = .idle
                }
            }
        }
    }
}

// MARK: - 通知名称

extension Notification.Name {
    public static let mp5RecordingCompleted = Notification.Name("mp5RecordingCompleted")
}
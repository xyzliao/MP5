//
// RecordViewModel.swift
// MP5iOS
//
// 录制ViewModel — 管理录制状态和完成后数据保存
//
// 对应 Android版 RecordScreen 中的数据逻辑。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import Foundation
import SwiftUI
import SwiftData
import MP5Core

@MainActor
public class RecordViewModel: ObservableObject {

    public let recorder = Mp5Recorder()

    @Published public var state: RecorderState = .idle
    @Published public var elapsedMs: Int64 = 0
    @Published public var currentLocation: GpsSample?
    @Published public var gpsSampleCount: Int = 0

    private var cancellables = Set<AnyCancellable>()

    public init() {
        // 绑定recorder状态
        recorder.$state
            .receive(on: DispatchQueue.main)
            .assign(to: &$state)

        recorder.$elapsedMs
            .receive(on: DispatchQueue.main)
            .assign(to: &$elapsedMs)

        recorder.$currentLocation
            .receive(on: DispatchQueue.main)
            .assign(to: &$currentLocation)

        recorder.$gpsSampleCount
            .receive(on: DispatchQueue.main)
            .assign(to: &$gpsSampleCount)
    }

    /// 请求权限
    public func requestPermissions() {
        recorder.requestPermissions()
    }

    /// 开始录制
    public func start() {
        recorder.start()
    }

    /// 暂停
    public func pause() {
        recorder.pause()
    }

    /// 继续
    public func resume() {
        recorder.resume()
    }

    /// 停止
    public func stop() {
        recorder.stop()
    }

    /// 添加POI
    public func addPoi(label: String? = nil) {
        recorder.addPoi(label: label)
    }

    /// 监听录制完成通知，保存到数据库
    public func handleRecordingCompleted(notification: Notification, context: ModelContext) {
        guard let info = notification.userInfo else { return }

        let record = Mp5FileRecord(
            filePath: info["filePath"] as? String ?? "",
            fileName: info["fileName"] as? String ?? "",
            fileSize: Int64(info["fileSize"] as? Int ?? 0),
            durationMs: info["durationMs"] as? Int64 ?? 0,
            startLat: info["startLat"] as? Double ?? 0,
            startLon: info["startLon"] as? Double ?? 0,
            endLat: info["endLat"] as? Double ?? 0,
            endLon: info["endLon"] as? Double ?? 0,
            totalDistanceKm: info["totalDistanceKm"] as? Double ?? 0,
            maxSpeedKmh: info["maxSpeedKmh"] as? Double ?? 0,
            gpsPointCount: info["gpsPointCount"] as? Int ?? 0
        )
        context.insert(record)
        try? context.save()
    }
}
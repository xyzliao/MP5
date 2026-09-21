//
// PlaybackViewModel.swift
// MP5iOS
//
// 播放ViewModel — 管理AVPlayer视频播放 + GPS同步
//
// 对应 Android版 Mp5PlayerController。
// 使用 AVPlayer.addPeriodicTimeObserver 替代轮询线程，20fps更新。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation
import AVFoundation
import Combine
import MP5Core

@MainActor
public class PlaybackViewModel: ObservableObject {

    @Published public var currentPositionMs: Int64 = 0
    @Published public var durationMs: Int64 = 0
    @Published public var isPlaying = false
    @Published public var currentGps: (Double, Double)?
    @Published public var gpsSamples: [GpsSample] = []
    @Published public var pois: [Poi] = []
    @Published public var syncRules = SyncRules()
    @Published public var isMp5 = false
    @Published public var totalDistance: Double = 0
    @Published public var maxSpeed: Double = 0
    @Published public var viewMode: ViewMode = .splitLR
    @Published public var fileInfo: Mp5Info?

    public private(set) var player: AVPlayer?
    private var timeObserver: Any?
    private var parser: Mp5Parser?
    private var syncEngine: SyncEngine?

    /// 加载MP5文件
    public func loadFile(_ url: URL) {
        guard let data = try? Data(contentsOf: url) else {
            print("无法读取文件: \(url.path)")
            return
        }

        let info = Mp5Parser.parse(data)
        fileInfo = info
        isMp5 = info.isMp5
        gpsSamples = info.gpsSamples
        pois = info.pois
        syncRules = info.syncRules
        totalDistance = Mp5Parser.getTotalDistance(samples: info.gpsSamples)
        maxSpeed = Mp5Parser.getMaxSpeed(samples: info.gpsSamples)

        // 设置默认视图模式
        viewMode = ViewMode(rawValue: info.syncRules.defaultView) ?? .splitLR

        // 初始化同步引擎
        syncEngine = SyncEngine(gpsSamples: info.gpsSamples, syncRules: info.syncRules)

        // 初始化AVPlayer
        // AVPlayer可以直接播放MP5文件（视频部分兼容MP4）
        let playerItem = AVPlayerItem(url: url)
        player = AVPlayer(playerItem: playerItem)

        // 获取时长
        if let duration = playerItem.asset.loadDurationSync() {
            durationMs = Int64(CMTimeGetSeconds(duration) * 1000)
        }

        // 添加周期性时间观察器（20fps = 每50ms）
        let interval = CMTime(seconds: 0.05, preferredTimescale: 600)
        timeObserver = player?.addPeriodicTimeObserver(
            forInterval: interval,
            queue: .main
        ) { [weak self] time in
            self?.onTimeUpdated(time)
        }

        // 监听播放状态
        player?.publisher(for: \\.timeControlStatus)
            .sink { [weak self] status in
                self?.isPlaying = (status == .playing)
            }
            .store(in: &cancellables)

        // 文件加载完成后自动播放
        play()
    }

    private var cancellables = Set<AnyCancellable>()

    private func onTimeUpdated(_ time: CMTime) {
        let pos = Int64(CMTimeGetSeconds(time) * 1000)
        currentPositionMs = pos

        // 查询当前GPS位置
        if let engine = syncEngine, !gpsSamples.isEmpty {
            if let gps = engine.getGpsAtTime(pos) {
                currentGps = (gps.latitude, gps.longitude)
            }
        }
    }

    /// 播放
    public func play() {
        player?.play()
    }

    /// 暂停 — AVPlayer.pause() 天然保持位置
    public func pause() {
        player?.pause()
    }

    /// 跳转到指定时间
    public func seekTo(ms: Int64) {
        let time = CMTime(seconds: Double(ms) / 1000, preferredTimescale: 600)
        player?.seek(to: time)
    }

    /// 地图→视频：点击地图坐标，跳转到对应视频时间
    public func seekToGps(lat: Double, lon: Double) {
        if let engine = syncEngine,
           let timestamp = engine.findNearestTimestamp(lat: lat, lon: lon) {
            seekTo(ms: timestamp)
        }
    }

    /// 释放资源
    public func release() {
        if let observer = timeObserver {
            player?.removeTimeObserver(observer)
            timeObserver = nil
        }
        player?.pause()
        player = nil
        cancellables.removeAll()
    }
}

// MARK: - AVAsset 扩展

extension AVAsset {
    /// 同步加载时长
    func loadDurationSync() -> CMTime? {
        var result: CMTime?
        let semaphore = DispatchSemaphore(value: 0)
        load(.duration) { duration, _ in
            result = duration
            semaphore.signal()
        }
        semaphore.wait()
        return result
    }
}
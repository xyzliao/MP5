//
// GpsCollector.swift
// MP5iOS
//
// GPS采集器 — 使用 CoreLocation 获取GPS坐标
//
// 采样率可配置：1Hz（步行）、5Hz（驾车）、10Hz（高速运动）
// 提供实时位置状态供UI订阅
//
// 对应 Android版 GpsCollector（FusedLocationProvider）。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation
import CoreLocation
import MP5Core

/// GPS采集器
public class GpsCollector: NSObject, CLLocationManagerDelegate {

    private let manager = CLLocationManager()
    private var samples: [GpsSample] = []
    private var startTimeMs: Int64 = 0
    private var paused = false
    private var sampleRateHz: Int = 1

    // 回调
    public var onLocationUpdate: ((GpsSample) -> Void)?
    public var onSampleCountChange: ((Int) -> Void)?

    public var currentLocation: GpsSample?
    public var sampleCount: Int { samples.count }

    public override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.activityType = .fitness
        manager.distanceFilter = kCLDistanceFilterNone
    }

    /// 请求定位权限
    public func requestPermission() {
        manager.requestWhenInUseAuthorization()
    }

    /// 是否有定位权限
    public var hasPermission: Bool {
        let status = manager.authorizationStatus
        return status == .authorizedAlways || status == .authorizedWhenInUse
    }

    /// 开始采集
    /// - Parameters:
    ///   - sampleRateHz: 采样率（Hz）
    ///   - startTimeMs: 起始时间戳（毫秒）
    public func start(sampleRateHz: Int = 1, startTimeMs: Int64) {
        self.sampleRateHz = sampleRateHz
        self.startTimeMs = startTimeMs
        samples.removeAll()
        paused = false
        currentLocation = nil
        onSampleCountChange?(0)

        if !hasPermission {
            requestPermission()
        }

        manager.startUpdatingLocation()
    }

    /// 停止采集，返回所有采样点
    public func stop() -> [GpsSample] {
        manager.stopUpdatingLocation()
        paused = false
        return samples
    }

    /// 获取当前采样点列表
    public func getCurrentSamples() -> [GpsSample] {
        return samples
    }

    /// 暂停GPS采样
    public func pause() {
        paused = true
        // 暂停时降低频率至0.1Hz（每10秒一次）
        // 与设计文档3.4节一致
    }

    /// 恢复GPS采样
    public func resume() {
        paused = false
    }

    /// 添加POI标记
    public func addPoi(label: String? = nil) {
        guard let current = currentLocation else { return }
        let poiSample = GpsSample(
            timestampMs: current.timestampMs,
            latitudeE7: current.latitudeE7,
            longitudeE7: current.longitudeE7,
            altitudeDm: current.altitudeDm,
            accuracyM: current.accuracyM,
            headingDeg: current.headingDeg,
            speedKmhX10: current.speedKmhX10,
            isPoi: true,
            poiLabel: label
        )
        samples.append(poiSample)
        onSampleCountChange?(samples.count)
    }

    // MARK: - CLLocationManagerDelegate

    public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard !paused, let location = locations.last else { return }

        let timestamp = Int64(Date().timeIntervalSince1970 * 1000) - startTimeMs
        let sample = GpsSample.fromDegrees(
            timestampMs: timestamp,
            latitude: location.coordinate.latitude,
            longitude: location.coordinate.longitude,
            altitudeM: location.altitude,
            accuracyM: Int(location.horizontalAccuracy),
            headingDeg: Int(location.course),
            speedKmh: location.speed * 3.6
        )

        samples.append(sample)
        currentLocation = sample
        onLocationUpdate?(sample)
        onSampleCountChange?(samples.count)
    }

    public func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
        print("GPS采集错误: \(error.localizedDescription)")
    }
}
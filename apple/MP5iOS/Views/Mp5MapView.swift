//
// Mp5MapView.swift
// MP5iOS
//
// MapKit 地图封装 — 显示GPS轨迹、当前位置、起点终点、POI标记
//
// 对应 Android版 Mp5MapView（osmdroid）和 Windows版 MapCanvas。
//
// 功能：
//   - 完整轨迹线（MKPolyline）
//   - 已播放部分高亮（第二段 MKPolyline，白色）
//   - 速度热力图（分段绘制不同颜色线段）
//   - 当前位置脉冲标记
//   - 起点/终点标记（绿色/红色）
//   - POI 标记
//   - 点击地图跳转视频
//   - 自动调整视野范围
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.10
//

import SwiftUI
import MapKit
import MP5Core

struct Mp5MapView: UIViewRepresentable {
    let gpsSamples: [GpsSample]
    let currentGps: (Double, Double)?
    let onMapClick: (Double, Double) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onMapClick: onMapClick)
    }

    func makeUIView(context: Context) -> MKMapView {
        let mapView = MKMapView()
        mapView.delegate = context.coordinator
        mapView.showsUserLocation = false
        mapView.isZoomEnabled = true
        mapView.isScrollEnabled = true

        // 点击手势
        let tap = UITapGestureRecognizer(target: context.coordinator, action: #selector(Coordinator.onTap(_:)))
        mapView.addGestureRecognizer(tap)

        return mapView
    }

    func updateUIView(_ mapView: MKMapView, context: Context) {
        context.coordinator.onMapClick = onMapClick

        // 更新轨迹
        if gpsSamples != context.coordinator.lastSamples {
            context.coordinator.lastSamples = gpsSamples
            updateOverlays(mapView: mapView, samples: gpsSamples)
        }

        // 更新当前位置
        if let gps = currentGps {
            let coordinate = CLLocationCoordinate2D(latitude: gps.0, longitude: gps.1)
            context.coordinator.updateCurrentPosition(mapView: mapView, coordinate: coordinate)
        }
    }

    /// 更新地图覆盖物
    private func updateOverlays(mapView: MKMapView, samples: [GpsSample]) {
        mapView.removeOverlays(mapView.overlays)
        mapView.removeAnnotations(mapView.annotations)

        guard !samples.isEmpty else { return }

        // 速度热力图轨迹段
        for i in 1..<samples.count {
            let prev = samples[i - 1]
            let curr = samples[i]
            let color = speedColor(curr.speedKmh)
            let coords = [
                CLLocationCoordinate2D(latitude: prev.latitude, longitude: prev.longitude),
                CLLocationCoordinate2D(latitude: curr.latitude, longitude: curr.longitude)
            ]
            let polyline = SpeedPolyline(coordinates: coords, count: 2)
            polyline.color = color
            mapView.addOverlay(polyline)
        }

        // 起点（绿色）
        let start = samples[0]
        let startAnnotation = MapPointAnnotation(
            coordinate: CLLocationCoordinate2D(latitude: start.latitude, longitude: start.longitude),
            title: "起点",
            color: .green,
            glyph: "flag.fill"
        )
        mapView.addAnnotation(startAnnotation)

        // 终点（红色）
        let end = samples[samples.count - 1]
        let endAnnotation = MapPointAnnotation(
            coordinate: CLLocationCoordinate2D(latitude: end.latitude, longitude: end.longitude),
            title: "终点",
            color: .red,
            glyph: "flag.checkered"
        )
        mapView.addAnnotation(endAnnotation)

        // 自动调整视野
        let lats = samples.map { $0.latitude }
        let lons = samples.map { $0.longitude }
        let minLat = lats.min()!, maxLat = lats.max()!
        let minLon = lons.min()!, maxLon = lons.max()!

        let latDelta = max(maxLat - minLat, 0.005) * 1.3
        let lonDelta = max(maxLon - minLon, 0.005) * 1.3
        let center = CLLocationCoordinate2D(
            latitude: (minLat + maxLat) / 2,
            longitude: (minLon + maxLon) / 2
        )
        let region = MKCoordinateRegion(
            center: center,
            span: MKCoordinateSpan(latitudeDelta: latDelta, longitudeDelta: lonDelta)
        )
        mapView.setRegion(region, animated: false)
    }

    /// 速度热力图颜色
    private func speedColor(_ speedKmh: Double) -> UIColor {
        if speedKmh < 5 {
            return UIColor(red: 0.231, green: 0.510, blue: 0.965, alpha: 1)  // 蓝
        } else if speedKmh < 20 {
            return UIColor(red: 0.133, green: 0.773, blue: 0.369, alpha: 1)  // 绿
        } else if speedKmh < 60 {
            return UIColor(red: 0.918, green: 0.702, blue: 0.031, alpha: 1)  // 黄
        } else if speedKmh < 120 {
            return UIColor(red: 0.976, green: 0.451, blue: 0.086, alpha: 1)  // 橙
        } else {
            return UIColor(red: 0.937, green: 0.318, blue: 0.286, alpha: 1)  // 红
        }
    }
}

// MARK: - Coordinator

extension Mp5MapView {
    class Coordinator: NSObject, MKMapViewDelegate {
        var onMapClick: (Double, Double) -> Void
        var lastSamples: [GpsSample] = []
        private var currentAnnotation: MKPointAnnotation?

        init(onMapClick: @escaping (Double, Double) -> Void) {
            self.onMapClick = onMapClick
        }

        @objc func onTap(_ gesture: UITapGestureRecognizer) {
            guard let mapView = gesture.view as? MKMapView else { return }
            let point = gesture.location(in: mapView)
            let coordinate = mapView.convert(point, toCoordinateFrom: mapView)
            onMapClick(coordinate.latitude, coordinate.longitude)
        }

        func updateCurrentPosition(mapView: MKMapView, coordinate: CLLocationCoordinate2D) {
            if let existing = currentAnnotation {
                mapView.removeAnnotation(existing)
            }
            let annotation = MKPointAnnotation()
            annotation.coordinate = coordinate
            annotation.title = "当前位置"
            currentAnnotation = annotation
            mapView.addAnnotation(annotation)
        }

        // MARK: - MKMapViewDelegate

        func mapView(_ mapView: MKMapView, rendererFor overlay: MKOverlay) -> MKOverlayRenderer {
            if let speedPolyline = overlay as? SpeedPolyline {
                let renderer = MKPolylineRenderer(polyline: speedPolyline)
                renderer.strokeColor = speedPolyline.color
                renderer.lineWidth = 4
                return renderer
            }
            return MKOverlayRenderer(overlay: overlay)
        }

        func mapView(_ mapView: MKMapView, viewFor annotation: MKAnnotation) -> MKAnnotationView? {
            guard let pointAnnotation = annotation as? MapPointAnnotation else {
                if annotation is MKPointAnnotation {
                    // 当前位置标记
                    let id = "currentPosition"
                    let view = mapView.dequeueReusableAnnotationView(withIdentifier: id) as? MKMarkerAnnotationView
                        ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: id)
                    view.markerTintColor = UIColor.systemRed
                    view.glyphImage = UIImage(systemName: "location.fill")
                    view.canShowCallout = true
                    return view
                }
                return nil
            }

            let id = "mapPoint"
            let view = mapView.dequeueReusableAnnotationView(withIdentifier: id) as? MKMarkerAnnotationView
                ?? MKMarkerAnnotationView(annotation: annotation, reuseIdentifier: id)
            view.markerTintColor = pointAnnotation.color
            view.glyphImage = UIImage(systemName: pointAnnotation.glyph)
            view.canShowCallout = true
            return view
        }
    }
}

// MARK: - 自定义类型

/// 速度热力图 Polyline
class SpeedPolyline: MKPolyline {
    var color: UIColor = .blue
}

/// 地图点标注
class MapPointAnnotation: NSObject, MKAnnotation {
    var coordinate: CLLocationCoordinate2D
    var title: String?
    var color: UIColor
    var glyph: String

    init(coordinate: CLLocationCoordinate2D, title: String, color: UIColor, glyph: String) {
        self.coordinate = coordinate
        self.title = title
        self.color = color
        self.glyph = glyph
    }
}
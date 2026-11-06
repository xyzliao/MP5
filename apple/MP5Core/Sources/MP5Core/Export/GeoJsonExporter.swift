//
// GeoJsonExporter.swift
// MP5Core
//
// GeoJSON 导出器 — 将GPS采样点导出为GeoJSON FeatureCollection
//
// 与 Windows版 export_geojson() 对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation

/// GeoJSON 导出器
public enum GeoJsonExporter {

    /// 导出 GeoJSON 格式字符串
    public static func export(samples: [GpsSample], pois: [Poi] = []) -> String {
        var features: [[String: Any]] = []

        // 轨迹 LineString
        let coordinates = samples.map { [$0.longitude, $0.latitude, $0.altitudeM] as [Double] }
        features.append([
            "type": "Feature",
            "properties": [
                "name": "MP5 Track",
                "creator": "MP5录播器",
                "pointCount": samples.count
            ] as [String: Any],
            "geometry": [
                "type": "LineString",
                "coordinates": coordinates
            ] as [String: Any]
        ])

        // POI 标记
        for poi in pois {
            features.append([
                "type": "Feature",
                "properties": [
                    "name": poi.label,
                    "type": poi.type,
                    "timestamp": poi.timestampMs
                ] as [String: Any],
                "geometry": [
                    "type": "Point",
                    "coordinates": [poi.longitude, poi.latitude]
                ] as [String: Any]
            ])
        }

        let geoJson: [String: Any] = [
            "type": "FeatureCollection",
            "features": features
        ]

        let data = try? JSONSerialization.data(withJSONObject: geoJson, options: [.prettyPrinted, .withoutEscapingSlashes])
        return data.map { String(data: $0, encoding: .utf8) ?? "{}" } ?? "{}"
    }

    /// 导出 GeoJSON 文件
    public static func exportFile(samples: [GpsSample], pois: [Poi] = [], to url: URL) throws {
        let json = export(samples: samples, pois: pois)
        try json.write(to: url, atomically: true, encoding: .utf8)
    }
}
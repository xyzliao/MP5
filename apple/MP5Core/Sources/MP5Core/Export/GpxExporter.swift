//
// GpxExporter.swift
// MP5Core
//
// GPX 导出器 — 将GPS采样点导出为标准GPX 1.1文件
//
// 与 Windows版 export_gpx() 和 Android版 GpxExporter 对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.21
//

import Foundation

/// GPX 导出器
public enum GpxExporter {

    /// 导出 GPX 格式 XML 字符串
    public static func export(samples: [GpsSample], pois: [Poi] = []) -> String {
        let dateFormatter = ISO8601DateFormatter()
        dateFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        var lines: [String] = []
        lines.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        lines.append("<gpx version=\"1.1\" creator=\"MP5录播器\" xmlns=\"http://www.topografix.com/GPX/1/1\">")
        lines.append("  <metadata>")
        lines.append("    <name>MP5 GPS Track</name>")
        lines.append("    <time>\(dateFormatter.string(from: Date()))</time>")
        lines.append("  </metadata>")

        // POI waypoints
        for poi in pois {
            lines.append("  <wpt lat=\"\(String(format: "%.7f", poi.latitude))\" lon=\"\(String(format: "%.7f", poi.longitude))\">")
            lines.append("    <name>\(escapeXml(poi.label))</name>")
            lines.append("  </wpt>")
        }

        // Track
        lines.append("  <trk>")
        lines.append("    <name>MP5 Track</name>")
        lines.append("    <trkseg>")

        for s in samples {
            lines.append("      <trkpt lat=\"\(String(format: "%.7f", s.latitude))\" lon=\"\(String(format: "%.7f", s.longitude))\">")
            lines.append("        <ele>\(String(format: "%.1f", s.altitudeM))</ele>")
            // 使用相对于2000-01-01的偏移作为时间
            let time = Date(timeIntervalSince1970: TimeInterval(s.timestampMs) / 1000)
            lines.append("        <time>\(dateFormatter.string(from: time))</time>")
            if s.speedKmh > 0 {
                lines.append("        <extensions><speed>\(String(format: "%.2f", s.speedKmh / 3.6))</speed></extensions>")
            }
            lines.append("      </trkpt>")
        }

        lines.append("    </trkseg>")
        lines.append("  </trk>")
        lines.append("</gpx>")

        return lines.joined(separator: "\n")
    }

    /// 导出 GPX 文件
    public static func exportFile(samples: [GpsSample], pois: [Poi] = [], to url: URL) throws {
        let gpx = export(samples: samples, pois: pois)
        try gpx.write(to: url, atomically: true, encoding: .utf8)
    }

    private static func escapeXml(_ text: String) -> String {
        text
            .replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
            .replacingOccurrences(of: "\"", with: "&quot;")
            .replacingOccurrences(of: "'", with: "&apos;")
    }
}
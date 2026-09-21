//
// KmlExporter.swift
// MP5Core
//
// KML 导出器 — 将GPS采样点导出为KML格式 (Google Earth)
//
// 与 Windows版 export_kml() 对齐。
//
// 作者: 大米斗（Aniseedaliao）
// 版本: 1.0.20
//

import Foundation

/// KML 导出器
public enum KmlExporter {

    /// 导出 KML 格式字符串
    public static func export(samples: [GpsSample], pois: [Poi] = []) -> String {
        var lines: [String] = []
        lines.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>")
        lines.append("<kml xmlns=\"http://www.opengis.net/kml/2.2\">")
        lines.append("  <Document>")
        lines.append("    <name>MP5 Track</name>")
        lines.append("    <Style id=\"trackStyle\">")
        lines.append("      <LineStyle><color>ff0066ff</color><width>3</width></LineStyle>")
        lines.append("    </Style>")

        // POI 标记
        for poi in pois {
            lines.append("    <Placemark>")
            lines.append("      <name>\(escapeXml(poi.label))</name>")
            lines.append("      <Point>")
            lines.append("        <coordinates>\(poi.longitude),\(poi.latitude),0</coordinates>")
            lines.append("      </Point>")
            lines.append("    </Placemark>")
        }

        // 轨迹
        lines.append("    <Placemark>")
        lines.append("      <name>MP5 Track</name>")
        lines.append("      <styleUrl>#trackStyle</styleUrl>")
        lines.append("      <LineString>")
        lines.append("        <coordinates>")
        for s in samples {
            lines.append("          \(s.longitude),\(s.latitude),\(s.altitudeM)")
        }
        lines.append("        </coordinates>")
        lines.append("      </LineString>")
        lines.append("    </Placemark>")

        lines.append("  </Document>")
        lines.append("</kml>")

        return lines.joined(separator: "\n")
    }

    /// 导出 KML 文件
    public static func exportFile(samples: [GpsSample], pois: [Poi] = [], to url: URL) throws {
        let kml = export(samples: samples, pois: pois)
        try kml.write(to: url, atomically: true, encoding: .utf8)
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
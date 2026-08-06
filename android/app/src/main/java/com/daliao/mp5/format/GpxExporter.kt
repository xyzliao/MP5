package com.daliao.mp5.format

import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * GPX导出器 — 将GPS采样点导出为标准GPX 1.1文件
 */
object GpxExporter {

    fun export(samples: List<GpsSample>, outputFile: File) {
        val dateFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
        dateFormat.timeZone = TimeZone.getTimeZone("UTC")

        val sb = StringBuilder()
        sb.append("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n")
        sb.append("<gpx version=\"1.1\" creator=\"MP5录播器\" ")
        sb.append("xmlns=\"http://www.topografix.com/GPX/1/1\">\n")
        sb.append("  <metadata>\n")
        sb.append("    <name>MP5 GPS Track</name>\n")
        sb.append("    <time>${dateFormat.format(Date())}</time>\n")
        sb.append("  </metadata>\n")
        sb.append("  <trk>\n")
        sb.append("    <name>MP5 Track</name>\n")
        sb.append("    <trkseg>\n")

        for (s in samples) {
            sb.append("      <trkpt lat=\"${s.latitude}\" lon=\"${s.longitude}\">\n")
            sb.append("        <ele>${s.altitudeM}</ele>\n")
            sb.append("        <time>${dateFormat.format(Date(s.timestampMs))}</time>\n")
            if (s.speedKmh > 0) {
                sb.append("        <speed>${s.speedKmh / 3.6}</speed>\n") // m/s
            }
            if (s.headingDeg > 0) {
                sb.append("        <course>${s.headingDeg}</course>\n")
            }
            if (s.isPoi && s.poiLabel != null) {
                sb.append("        <name>${escapeXml(s.poiLabel)}</name>\n")
            }
            sb.append("      </trkpt>\n")
        }

        sb.append("    </trkseg>\n")
        sb.append("  </trk>\n")
        sb.append("</gpx>\n")

        outputFile.writeText(sb.toString())
    }

    private fun escapeXml(text: String): String {
        return text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&apos;")
    }
}
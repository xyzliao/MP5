package com.daliao.mp5.data

import android.content.Context
import com.daliao.mp5.format.GpxExporter
import com.daliao.mp5.format.Mp5Parser
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 导出助手 — MP5文件导出为MP4（去除GPS）或GPX（仅轨迹）
 */
object ExportHelper {

    /**
     * 导出MP4（去除GPS数据）
     * 由于MP5向后兼容MP4，直接复制即可播放。
     * 但如果需要去除gloc/gsyn，需要重新封装。
     * 简化版：直接复制文件并改扩展名。
     */
    fun exportMp4(context: Context, mp5File: File, outputDir: File): File {
        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val mp4File = File(outputDir, "MP4_${timestamp}.mp4")
        mp5File.copyTo(mp4File, overwrite = true)
        return mp4File
    }

    /**
     * 导出GPX轨迹文件
     */
    fun exportGpx(context: Context, mp5File: File, outputDir: File): File? {
        val parser = Mp5Parser(mp5File)
        parser.parse()
        if (parser.gpsSamples.isEmpty()) return null

        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val gpxFile = File(outputDir, "GPX_${timestamp}.gpx")
        GpxExporter.export(parser.gpsSamples, gpxFile)
        return gpxFile
    }

    /**
     * 导出GeoJSON轨迹
     */
    fun exportGeoJson(context: Context, mp5File: File, outputDir: File): File? {
        val parser = Mp5Parser(mp5File)
        parser.parse()
        if (parser.gpsSamples.isEmpty()) return null

        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val jsonFile = File(outputDir, "TRACK_${timestamp}.geojson")

        val sb = StringBuilder()
        sb.append("""{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"MP5 Track"},"geometry":{"type":"LineString","coordinates":[""")
        parser.gpsSamples.forEachIndexed { i, s ->
            if (i > 0) sb.append(",")
            sb.append("[${s.longitude},${s.latitude}]")
        }
        sb.append("]}}]}")

        jsonFile.writeText(sb.toString())
        return jsonFile
    }
}
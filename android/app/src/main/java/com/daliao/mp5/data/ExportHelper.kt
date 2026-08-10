package com.daliao.mp5.data

import android.content.Context
import com.daliao.mp5.format.GpxExporter
import com.daliao.mp5.format.Mp5Box
import com.daliao.mp5.format.Mp5Parser
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 导出助手 — MP5文件导出为MP4（去除GPS）或GPX（仅轨迹）
 *
 * @author 大米斗（Aniseedaliao）
 */
object ExportHelper {

    /**
     * 导出MP4（真正剥离MP5扩展box：gloc/gsyn/gmap/gpoi）
     *
     * 流程：
     * 1. 用RandomAccessFile解析box结构
     * 2. 找到gloc/gsyn/gmap/gpoi box的偏移和大小
     * 3. 移除这些box，写入新文件
     * 4. 修正moov的size和stco/co64偏移
     */
    fun exportMp4(context: Context, mp5File: File, outputDir: File): File {
        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val mp4File = File(outputDir, "MP4_${timestamp}.mp4")

        RandomAccessFile(mp5File, "r").use { raf ->
            val fileLength = raf.length()
            val mp5Types = setOf(Mp5Box.GLOC, Mp5Box.GMAP, Mp5Box.GSYN, Mp5Box.GPOI)

            // 收集需要移除的box范围
            val ranges = mutableListOf<Pair<Long, Long>>()
            var offset = 0L
            while (offset + 8 <= fileLength) {
                raf.seek(offset)
                val size = raf.readInt().toLong() and 0xFFFFFFFFL
                val typeInt = raf.readInt()
                if (size < 8) break

                val type = Mp5Box.intToFourCc(typeInt)
                if (type in mp5Types) {
                    ranges.add(Pair(offset, offset + size))
                }

                offset += size
            }

            if (ranges.isEmpty()) {
                // 没有MP5扩展box，直接复制
                raf.seek(0)
                mp4File.outputStream().use { out ->
                    val buffer = ByteArray(8192)
                    var remaining = fileLength
                    while (remaining > 0) {
                        val toRead = minOf(remaining.toInt(), buffer.size)
                        raf.readFully(buffer, 0, toRead)
                        out.write(buffer, 0, toRead)
                        remaining -= toRead
                    }
                }
                return mp4File
            }

            // 计算原始mdat的数据偏移
            raf.seek(0)
            val mdatBox = Mp5Box.findBox(raf, Mp5Box.MDAT, 0)
            val origMdatDataOffset = if (mdatBox != null) mdatBox.first + 8 else 0L

            // 计算移除的总大小
            val totalRemoved = ranges.sumOf { it.second - it.first }

            // 构建新数据：跳过MP5 box范围
            val tempFile = File(outputDir, "MP4_${timestamp}_tmp.mp4")
            RandomAccessFile(tempFile, "rw").use { output ->
                var prevEnd = 0L
                for ((start, end) in ranges) {
                    // 复制 prevEnd 到 start
                    if (start > prevEnd) {
                        copyRange(raf, output, prevEnd, start - prevEnd)
                    }
                    prevEnd = end
                }
                // 复制剩余部分
                if (prevEnd < fileLength) {
                    copyRange(raf, output, prevEnd, fileLength - prevEnd)
                }

                // 修正stco/co64偏移量（mdat前移了totalRemoved字节）
                val newMdatBox = Mp5Box.findBox(output, Mp5Box.MDAT, 0)
                val newMdatDataOffset = if (newMdatBox != null) newMdatBox.first + 8 else 0L
                val delta = newMdatDataOffset - origMdatDataOffset

                if (delta != 0L) {
                    fixStcoOffsets(output, delta)
                }

                // 修正moov box size（如果moov在被移除的box之前，其size不变；
                // 如果moov包含被移除的box，需要修正size）
                // 实际上MP5扩展box在moov内部，所以需要修正moov size
                val moovBox = Mp5Box.findBox(output, Mp5Box.MOOV, 0)
                if (moovBox != null) {
                    // 重新计算moov实际内容大小
                    // 由于我们移除了moov内部的子box，moov的size应该减小
                    // 找到moov内部被移除的box
                    var removedInMoov = 0L
                    for ((start, end) in ranges) {
                        if (start > moovBox.first && end < moovBox.first + moovBox.second) {
                            removedInMoov += (end - start)
                        }
                    }
                    if (removedInMoov > 0) {
                        val newMoovSize = moovBox.second - removedInMoov
                        output.seek(moovBox.first)
                        val sizeBuf = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN)
                        sizeBuf.putInt(newMoovSize.toInt())
                        output.write(sizeBuf.array())
                    }
                }
            }

            // 重命名临时文件
            tempFile.renameTo(mp4File)
        }

        return mp4File
    }

    /**
     * 修正文件中所有stco/co64的偏移量
     *
     * @param file 已打开的RandomAccessFile
     * @param delta 偏移修正量（正数表示mdat后移，负数表示前移）
     */
    private fun fixStcoOffsets(file: RandomAccessFile, delta: Long) {
        if (delta == 0L) return

        val moovBox = Mp5Box.findBox(file, Mp5Box.MOOV, 0) ?: return

        // 递归查找所有stco/co64 box
        val stcoBoxes = Mp5Box.findAllBoxesInContainer(
            file, moovBox.first, moovBox.second,
            setOf(Mp5Box.STCO, Mp5Box.CO64)
        )

        for ((boxOffset, boxSize, _) in stcoBoxes) {
            // stco/co64 都是 FullBox: 8 header + 4 version/flags + 4 entry_count + entries
            file.seek(boxOffset + 12)
            val entryCount = file.readInt().toLong() and 0xFFFFFFFFL

            // 读取box类型判断是stco还是co64
            file.seek(boxOffset + 4)
            val type = Mp5Box.intToFourCc(file.readInt())

            if (type == Mp5Box.STCO) {
                // stco: 每个条目4字节
                for (i in 0 until entryCount) {
                    val entryPos = boxOffset + 16 + i * 4
                    file.seek(entryPos)
                    val oldVal = file.readInt().toLong() and 0xFFFFFFFFL
                    val newVal = oldVal + delta
                    file.seek(entryPos)
                    file.writeInt(newVal.toInt())
                }
            } else if (type == Mp5Box.CO64) {
                // co64: 每个条目8字节
                for (i in 0 until entryCount) {
                    val entryPos = boxOffset + 16 + i * 8
                    file.seek(entryPos)
                    val oldVal = file.readLong()
                    val newVal = oldVal + delta
                    file.seek(entryPos)
                    file.writeLong(newVal)
                }
            }
        }
    }

    /**
     * 复制文件中的一段到输出文件
     */
    private fun copyRange(input: RandomAccessFile, output: RandomAccessFile,
                          inputOffset: Long, length: Long) {
        if (length <= 0) return
        val buffer = ByteArray(8192)
        var remaining = length
        var inPos = inputOffset
        input.seek(inPos)
        while (remaining > 0) {
            val toRead = minOf(remaining.toInt(), buffer.size)
            input.readFully(buffer, 0, toRead)
            output.write(buffer, 0, toRead)
            remaining -= toRead
            inPos += toRead
        }
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
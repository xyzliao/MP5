package com.daliao.mp5.format

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * MP5 Muxer — 将GPS轨迹数据封装进MP4文件，生成MP5
 *
 * 流程：
 * 1. 录制完成后，得到一个标准MP4文件
 * 2. 将gloc、gsyn box插入到moov/meta容器中
 * 3. 修改ftyp的major_brand为mp5v
 * 4. 输出MP5文件
 *
 * 兼容性：不支持MP5的播放器会忽略gloc/gsyn，按mp41/isom正常播放视频
 */
class Mp5Muxer {

    // gloc Box数据
    private val gpsSamples = mutableListOf<GpsSample>()

    // gsyn Box配置
    var syncMode: Int = 0        // 0=时间同步, 1=最近邻, 2=插值
    var syncOffsetMs: Int = 0    // GPS时钟与视频时钟的偏移
    var interpolation: Int = 1   // 0=最近邻, 1=线性, 2=三次样条
    var defaultView: Int = 2     // 0=仅视频, 1=仅地图, 2=分屏左右, 3=分屏上下, 4=画中画
    var videoRatio: Float = 0.5f // 分屏视频占比
    var mapStyle: Int = 0        // 0=标准, 1=卫星, 2=地形, 3=暗色
    var showTrajectory: Int = 1   // 0=否, 1=是
    var showPoi: Int = 1          // 0=否, 1=是

    fun addGpsSample(sample: GpsSample) {
        gpsSamples.add(sample)
    }

    fun addGpsSamples(samples: List<GpsSample>) {
        gpsSamples.addAll(samples)
    }

    /**
     * 构建gloc Box的payload（不含Box header）
     *
     * 结构：
     *   entry_count(4)
     *   for each entry:
     *     timestamp(8) + latitude(8) + longitude(8) + altitude(4) +
     *     accuracy(2) + heading(2) + speed(2)
     *
     * 每个采样点 = 34字节
     */
    private fun buildGlocPayload(): ByteArray {
        val entrySize = 8 + 8 + 8 + 4 + 2 + 2 + 2 // 34 bytes
        val payloadSize = 4 + entrySize * gpsSamples.size
        val buf = ByteBuffer.allocate(payloadSize).order(ByteOrder.BIG_ENDIAN)

        // entry_count
        buf.putUInt32(gpsSamples.size.toLong())

        for (s in gpsSamples) {
            buf.putUInt64(s.timestampMs)        // timestamp
            buf.putInt64(s.latitudeE7)          // latitude ×10^7
            buf.putInt64(s.longitudeE7)         // longitude ×10^7
            buf.putInt32(s.altitudeDm)          // altitude ×10
            buf.putUInt16(s.accuracyM)          // accuracy
            buf.putUInt16(s.headingDeg)          // heading
            buf.putUInt16(s.speedKmhX10)        // speed ×10
        }

        return buf.array()
    }

    /**
     * 构建gsyn Box的payload
     *
     * 结构：
     *   sync_mode(1) + sync_offset(4) + interpolation(1) + default_view(1) +
     *   video_ratio(4) + map_style(1) + show_trajectory(1) + show_poi(1)
     *   = 14 bytes
     */
    private fun buildGsynPayload(): ByteArray {
        val buf = ByteBuffer.allocate(14).order(ByteOrder.BIG_ENDIAN)
        buf.putUInt8(syncMode)
        buf.putInt32(syncOffsetMs)
        buf.putUInt8(interpolation)
        buf.putUInt8(defaultView)
        buf.putFloat32(videoRatio)
        buf.putUInt8(mapStyle)
        buf.putUInt8(showTrajectory)
        buf.putUInt8(showPoi)
        return buf.array()
    }

    /**
     * 构建ftyp Box payload for MP5
     * major_brand=mp5v, minor_version=0, compatible_brands=[mp5v, mp41, isom]
     */
    private fun buildFtypPayload(): ByteArray {
        // 4 (major) + 4 (minor) + 4*3 (compatible) = 20 bytes
        val buf = ByteBuffer.allocate(20).order(ByteOrder.BIG_ENDIAN)
        buf.putFourCc("mp5v")    // major_brand
        buf.putUInt32(0)          // minor_version
        buf.putFourCc("mp5v")    // compatible_brand 1
        buf.putFourCc("mp41")    // compatible_brand 2
        buf.putFourCc("isom")    // compatible_brand 3
        return buf.array()
    }

    /**
     * 构建meta Box (FullBox) 包含 hdlr + gloc + gsyn
     */
    private fun buildMetaBox(): ByteArray {
        // hdlr payload: version(1)+flags(3) + pre_defined(4) + handler_type(4) + reserved(12) + name(1+)
        val hdlrPayload = ByteBuffer.allocate(25).order(ByteOrder.BIG_ENDIAN).apply {
            putInt(0)  // version+flags
            putInt(0)  // pre_defined
            putFourCc("mp5g") // handler_type: mp5 gps
            // reserved 12 bytes
            putInt(0); putInt(0); putInt(0)
            put(0) // name (null-terminated empty string)
        }.array()
        val hdlrBox = Mp5Box.buildBox(Mp5Box.HDLR, hdlrPayload)

        val glocBox = Mp5Box.buildFullBox(Mp5Box.GLOC, 0, 0, buildGlocPayload())
        val gsynBox = Mp5Box.buildFullBox(Mp5Box.GSYN, 0, 0, buildGsynPayload())

        // meta payload = version(1)+flags(3) + hdlr + gloc + gsyn
        val metaPayload = ByteBuffer.allocate(4 + hdlrBox.size + glocBox.size + gsynBox.size)
            .order(ByteOrder.BIG_ENDIAN)
        metaPayload.putUInt8(0)  // version
        metaPayload.put(byteArrayOf(0, 0, 0))  // flags
        metaPayload.put(hdlrBox)
        metaPayload.put(glocBox)
        metaPayload.put(gsynBox)

        return Mp5Box.buildBox(Mp5Box.META, metaPayload.array())
    }

    /**
     * 将MP4文件转换为MP5文件
     *
     * @param mp4File 输入的MP4文件
     * @param mp5File 输出的MP5文件
     */
    fun mux(mp4File: File, mp5File: File) {
        RandomAccessFile(mp4File, "r").use { input ->
            RandomAccessFile(mp5File, "rw").use { output ->
                val fileLength = input.length()

                // 1. 找到moov box
                val moovBox = Mp5Box.findBox(input, Mp5Box.MOOV, 0)
                    ?: throw IllegalStateException("No moov box found in MP4")

                // 2. 找到moov内部是否已有meta box
                val existingMeta = Mp5Box.findBox(
                    input, Mp5Box.META,
                    moovBox.first + 8, moovBox.first + moovBox.second
                )

                // 3. 构建新的meta box
                val metaBox = buildMetaBox()

                // 4. 计算插入后的文件大小
                val insertOffset = if (existingMeta != null) {
                    // 替换已有的meta box
                    existingMeta.first
                } else {
                    // 插入到moov box内部末尾
                    moovBox.first + moovBox.second
                }

                val oldMetaSize = if (existingMeta != null) existingMeta.second else 0
                val sizeDelta = metaBox.size - oldMetaSize

                // 5. 复制文件，插入/替换meta box
                // 先复制 moov 之前的部分（含ftyp替换）
                var pos = 0L

                // 找ftyp
                val ftypBox = Mp5Box.findBox(input, Mp5Box.FTYP, 0)
                if (ftypBox != null) {
                    // 复制ftyp之前的部分（应该没有）
                    if (ftypBox.first > 0) {
                        copyBytes(input, output, 0, 0, ftypBox.first)
                    }
                    // 写入新的ftyp
                    val newFtyp = Mp5Box.buildBox(Mp5Box.FTYP, buildFtypPayload())
                    output.write(newFtyp)
                    pos = ftypBox.first + ftypBox.second
                }

                // 复制到moov开始（或在moov内部插入meta）
                val moovStart = moovBox.first
                if (pos < moovStart) {
                    copyBytes(input, output, pos, output.filePointer(), moovStart - pos)
                }

                if (existingMeta != null) {
                    // moov中已有meta：复制moov header + moov内部到meta前 + 新meta + meta后到moov结束
                    // moov header (8 bytes)
                    copyBytes(input, output, moovStart, output.filePointer(), 8)
                    // moov内容到meta前
                    copyBytes(input, output, moovStart + 8, output.filePointer(),
                              existingMeta.first - moovStart - 8)
                    // 写入新meta
                    output.write(metaBox)
                    // 复制meta后到moov结束
                    val afterMeta = existingMeta.first + existingMeta.second
                    copyBytes(input, output, afterMeta, output.filePointer(),
                              moovStart + moovBox.second - afterMeta)
                    // 复制moov之后的所有内容
                    copyBytes(input, output, moovStart + moovBox.second, output.filePointer(),
                              fileLength - moovStart - moovBox.second)
                } else {
                    // moov中无meta：需要扩大moov box
                    // 1. 读取moov header并修改size
                    input.seek(moovStart)
                    val oldMoovSize = input.readInt().toLong() and 0xFFFFFFFFL
                    input.readInt() // skip type 'moov'

                    val newMoovSize = oldMoovSize + metaBox.size
                    val moovHeader = ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN)
                    moovHeader.putUInt32(newMoovSize)
                    moovHeader.putFourCc(Mp5Box.MOOV)
                    output.write(moovHeader.array())

                    // 2. 复制moov内部内容
                    copyBytes(input, output, moovStart + 8, output.filePointer(),
                              moovBox.second - 8)

                    // 3. 在moov末尾插入meta box
                    output.write(metaBox)

                    // 4. 复制moov之后的所有内容
                    copyBytes(input, output, moovStart + moovBox.second, output.filePointer(),
                              fileLength - moovStart - moovBox.second)
                }

                // 6. 修正moov box size (如果新插入了meta)
                if (existingMeta == null) {
                    // 重新写入moov的size
                    val newMoovSize = moovBox.second + metaBox.size
                    output.seek(moovStart)
                    val sizeBuf = ByteBuffer.allocate(4).order(ByteOrder.BIG_ENDIAN)
                    sizeBuf.putInt(newMoovSize.toInt())
                    output.write(sizeBuf.array())
                }
            }
        }
    }

    private fun copyBytes(input: RandomAccessFile, output: RandomAccessFile,
                          inputOffset: Long, outputOffset: Long, length: Long) {
        if (length <= 0) return
        val buffer = ByteArray(8192)
        var remaining = length
        var inPos = inputOffset
        input.seek(inPos)
        output.seek(outputOffset)
        while (remaining > 0) {
            val toRead = minOf(remaining.toInt(), buffer.size)
            input.readFully(buffer, 0, toRead)
            output.write(buffer, 0, toRead)
            remaining -= toRead
            inPos += toRead
        }
    }
}
package com.daliao.mp5.format

import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * MP5 Box — ISO BMFF Box的读写工具
 *
 * MP5基于ISO 14496-12 (ISO Base Media File Format)，
 * 通过新增自定义Box类型扩展MP4：gloc, gmap, gsyn
 *
 * Box结构：
 *   [size(4)] [type(4)] [payload(size-8)]
 *   FullBox:  [size(4)] [type(4)] [version(1)] [flags(3)] [payload]
 */
object Mp5Box {

    const val FTYP = "ftyp"
    const val MOOV = "moov"
    const val MVHD = "mvhd"
    const val TRAK = "trak"
    const val MDAT = "mdat"
    const val META = "meta"
    const val HDLR = "hdlr"
    const val GLOC = "gloc"  // GPS坐标轨迹 ← 新增
    const val GMAP = "gmap"  // 嵌入地图数据 ← 新增
    const val GSYN = "gsyn"  // 同步规则 ← 新增

    /** Box类型4字符码转为Int */
    fun fourCcToInt(type: String): Int {
        require(type.length == 4) { "Box type must be 4 chars: $type" }
        return (type[0].code shl 24) or
               (type[1].code shl 16) or
               (type[2].code shl 8) or
               type[3].code
    }

    /** Int转4字符码 */
    fun intToFourCc(value: Int): String {
        return String(charArrayOf(
            ((value shr 24) and 0xFF).toChar(),
            ((value shr 16) and 0xFF).toChar(),
            ((value shr 8) and 0xFF).toChar(),
            (value and 0xFF).toChar()
        ))
    }

    // ── 写入辅助 ──────────────────────────────────

    fun ByteBuffer.putFourCc(type: String): ByteBuffer {
        putInt(fourCcToInt(type))
        return this
    }

    fun ByteBuffer.putUInt32(value: Long): ByteBuffer {
        putInt(value.toInt())
        return this
    }

    fun ByteBuffer.putUInt64(value: Long): ByteBuffer {
        putLong(value)
        return this
    }

    fun ByteBuffer.putInt32(value: Int): ByteBuffer {
        putInt(value)
        return this
    }

    fun ByteBuffer.putInt64(value: Long): ByteBuffer {
        putLong(value)
        return this
    }

    fun ByteBuffer.putUInt16(value: Int): ByteBuffer {
        putShort(value.toShort())
        return this
    }

    fun ByteBuffer.putUInt8(value: Int): ByteBuffer {
        put(value.toByte())
        return this
    }

    fun ByteBuffer.putFloat32(value: Float): ByteBuffer {
        putFloat(value)
        return this
    }

    // ── 读取辅助 ──────────────────────────────────

    fun ByteBuffer.readUInt32(): Long = (int.toLong() and 0xFFFFFFFFL)
    fun ByteBuffer.readUInt64(): Long = long
    fun ByteBuffer.readInt32(): Int = int
    fun ByteBuffer.readInt64(): Long = long
    fun ByteBuffer.readUInt16(): Int = (short.toInt() and 0xFFFF)
    fun ByteBuffer.readUInt8(): Int = (get().toInt() and 0xFF)
    fun ByteBuffer.readFloat32(): Float = float
    fun ByteBuffer.readFourCc(): String = intToFourCc(int)

    /**
     * 构建一个完整的Box（含header）
     * @param type 4字符Box类型
     * @param payload Box内容（不含header）
     * @return 完整Box的字节数组
     */
    fun buildBox(type: String, payload: ByteArray): ByteArray {
        val size = 8 + payload.size
        val buf = ByteBuffer.allocate(size).order(ByteOrder.BIG_ENDIAN)
        buf.putUInt32(size.toLong())
        buf.putFourCc(type)
        buf.put(payload)
        return buf.array()
    }

    /**
     * 构建一个FullBox（含version+flags）
     * @param type 4字符Box类型
     * @param version 1字节版本号
     * @param flags 3字节flags
     * @param payload FullBox内容
     * @return 完整FullBox的字节数组
     */
    fun buildFullBox(type: String, version: Int, flags: Int, payload: ByteArray): ByteArray {
        val size = 12 + payload.size
        val buf = ByteBuffer.allocate(size).order(ByteOrder.BIG_ENDIAN)
        buf.putUInt32(size.toLong())
        buf.putFourCc(type)
        buf.putUInt8(version)
        // flags 3 bytes
        buf.put(((flags shr 16) and 0xFF).toByte())
        buf.put(((flags shr 8) and 0xFF).toByte())
        buf.put((flags and 0xFF).toByte())
        buf.put(payload)
        return buf.array()
    }

    /**
     * 在RandomAccessFile中查找指定类型的Box
     * @param file 已打开的文件
     * @param targetType 要查找的Box类型（4字符）
     * @param startOffset 搜索起始偏移
     * @param endOffset 搜索结束偏移（-1表示到文件末尾）
     * @return Pair(boxOffset, boxSize) 或 null
     */
    fun findBox(
        file: RandomAccessFile,
        targetType: String,
        startOffset: Long,
        endOffset: Long = -1L
    ): Pair<Long, Long>? {
        var offset = startOffset
        val end = if (endOffset < 0) file.length() else endOffset
        val targetInt = fourCcToInt(targetType)

        while (offset + 8 <= end) {
            file.seek(offset)
            val size = file.readInt().toLong() and 0xFFFFFFFFL
            val type = file.readInt()

            if (size < 8) break

            if (type == targetInt) {
                return Pair(offset, size)
            }

            // 特殊处理：meta是FullBox，需要跳过version+flags
            offset += size
        }
        return null
    }

    /**
     * 递归查找Box路径，如 moov/meta/gloc
     * @param file 已打开的文件
     * @param path Box类型路径
     * @return Pair(boxOffset, boxSize) 或 null
     */
    fun findBoxPath(file: RandomAccessFile, path: List<String>): Pair<Long, Long>? {
        var currentOffset = 0L
        var currentEnd = -1L
        var result: Pair<Long, Long>? = null

        for (type in path) {
            result = findBox(file, type, currentOffset, currentEnd)
                ?: return null
            currentOffset = result.first + 8  // 进入Box内部
            // 如果是FullBox，再跳过4字节
            if (type == "meta" || type == GLOC || type == GMAP || type == GSYN || type == MVHD || type == HDLR) {
                currentOffset += 4
            }
            currentEnd = result.first + result.second
        }
        return result
    }

    /**
     * 读取Box的payload（不含header）
     * @param file 已打开的文件
     * @param boxOffset Box起始偏移
     * @param boxSize Box总大小
     * @param isFullBox 是否为FullBox（含version+flags）
     * @return payload字节数组
     */
    fun readBoxPayload(
        file: RandomAccessFile,
        boxOffset: Long,
        boxSize: Long,
        isFullBox: Boolean = false
    ): ByteArray {
        val headerSize = if (isFullBox) 12 else 8
        val payloadSize = (boxSize - headerSize).toInt()
        if (payloadSize <= 0) return ByteArray(0)
        val payload = ByteArray(payloadSize)
        file.seek(boxOffset + headerSize)
        file.readFully(payload)
        return payload
    }
}
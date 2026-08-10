package com.daliao.mp5.format

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * MP5 Parser — 解析MP5文件，提取GPS轨迹和同步规则
 *
 * 1. 读取ftyp确认是MP5文件（major_brand=mp5v）
 * 2. 在moov/meta中查找gloc、gmap、gsyn、gpoi box
 * 3. 解析GPS采样点列表
 * 4. 向后兼容：如果无gloc box，则按普通MP4处理
 *
 * @author 大米斗（Aniseedaliao）
 */
class Mp5Parser(private val file: File) {

    data class SyncRules(
        val syncMode: Int = 0,
        val syncOffsetMs: Int = 0,
        val interpolation: Int = 1,
        val defaultView: Int = 2,
        val videoRatio: Float = 0.5f,
        val mapStyle: Int = 0,
        val showTrajectory: Boolean = true,
        val showPoi: Boolean = true
    )

    var isMp5: Boolean = false
        private set

    var gpsSamples: List<GpsSample> = emptyList()
        private set

    var syncRules: SyncRules = SyncRules()
        private set

    var pois: List<GpsSample> = emptyList()
        private set

    var hasMapData: Boolean = false
        private set

    /** 解析文件 */
    fun parse() {
        RandomAccessFile(file, "r").use { raf ->
            // 1. 检查ftyp
            val ftypBox = Mp5Box.findBox(raf, Mp5Box.FTYP, 0)
            if (ftypBox != null) {
                val payload = Mp5Box.readBoxPayload(raf, ftypBox.first, ftypBox.second)
                if (payload.size >= 4) {
                    val majorBrand = Mp5Box.intToFourCc(
                        ByteBuffer.wrap(payload, 0, 4).order(ByteOrder.BIG_ENDIAN).int
                    )
                    isMp5 = majorBrand == "mp5v"
                }
            }

            // 2. 查找 moov/meta/gloc
            val glocPath = Mp5Box.findBoxPath(raf, listOf(Mp5Box.MOOV, Mp5Box.META, Mp5Box.GLOC))
            if (glocPath != null) {
                val (offset, size) = glocPath
                val payload = Mp5Box.readBoxPayload(raf, offset, size, isFullBox = true)
                gpsSamples = parseGlocPayload(payload)
                isMp5 = true
            }

            // 3. 查找 moov/meta/gpoi
            val gpoiPath = Mp5Box.findBoxPath(raf, listOf(Mp5Box.MOOV, Mp5Box.META, Mp5Box.GPOI))
            if (gpoiPath != null) {
                val (offset, size) = gpoiPath
                val payload = Mp5Box.readBoxPayload(raf, offset, size, isFullBox = true)
                pois = parseGpoiPayload(payload)
            }

            // 4. 查找 moov/meta/gsyn
            val gsynPath = Mp5Box.findBoxPath(raf, listOf(Mp5Box.MOOV, Mp5Box.META, Mp5Box.GSYN))
            if (gsynPath != null) {
                val (offset, size) = gsynPath
                val payload = Mp5Box.readBoxPayload(raf, offset, size, isFullBox = true)
                syncRules = parseGsynPayload(payload)
            }

            // 5. 查找 moov/meta/gmap
            val gmapPath = Mp5Box.findBoxPath(raf, listOf(Mp5Box.MOOV, Mp5Box.META, Mp5Box.GMAP))
            hasMapData = gmapPath != null
        }
    }

    /**
     * 解析gloc Box payload
     *
     * entry_count(4)
     * for each: timestamp(8) + lat(8) + lon(8) + alt(4) + acc(2) + heading(2) + speed(2) = 34 bytes
     */
    private fun parseGlocPayload(payload: ByteArray): List<GpsSample> {
        if (payload.size < 4) return emptyList()
        val buf = ByteBuffer.wrap(payload).order(ByteOrder.BIG_ENDIAN)
        val entryCount = buf.readUInt32().toInt()
        if (entryCount <= 0) return emptyList()

        val samples = ArrayList<GpsSample>(entryCount)
        repeat(entryCount) {
            if (buf.remaining() < 34) return@repeat
            val timestampMs = buf.readUInt64()
            val latE7 = buf.readInt64()
            val lonE7 = buf.readInt64()
            val altDm = buf.readInt32()
            val acc = buf.readUInt16()
            val heading = buf.readUInt16()
            val speed = buf.readUInt16()
            samples.add(GpsSample(
                timestampMs = timestampMs,
                latitudeE7 = latE7,
                longitudeE7 = lonE7,
                altitudeDm = altDm,
                accuracyM = acc,
                headingDeg = heading,
                speedKmhX10 = speed
            ))
        }
        return samples
    }

    /**
     * 解析gpoi Box payload
     *
     * entry_count(4B)
     * for each poi:
     *   timestamp(8B) + latitudeE7(8B) + longitudeE7(8B) +
     *   label_length(2B) + label_bytes + type(1B)
     */
    private fun parseGpoiPayload(payload: ByteArray): List<GpsSample> {
        if (payload.size < 4) return emptyList()
        val buf = ByteBuffer.wrap(payload).order(ByteOrder.BIG_ENDIAN)
        val poiCount = buf.readUInt32().toInt()
        if (poiCount <= 0) return emptyList()

        val results = ArrayList<GpsSample>(poiCount)
        repeat(poiCount) {
            if (buf.remaining() < 27) return@repeat  // 8+8+8+2+0+1 = 27 (minimum)
            val timestampMs = buf.readUInt64()
            val latE7 = buf.readInt64()
            val lonE7 = buf.readInt64()
            val labelLen = buf.readUInt16()
            if (buf.remaining() < labelLen + 1) return@repeat
            val labelBytes = ByteArray(labelLen)
            buf.get(labelBytes)
            val label = String(labelBytes, Charsets.UTF_8)
            val typeByte = buf.readUInt8()
            val isPoi = typeByte != 0
            results.add(GpsSample(
                timestampMs = timestampMs,
                latitudeE7 = latE7,
                longitudeE7 = lonE7,
                altitudeDm = 0,
                accuracyM = 0,
                headingDeg = 0,
                speedKmhX10 = 0,
                isPoi = isPoi,
                poiLabel = if (label.isNotEmpty()) label else null
            ))
        }
        return results
    }

    /**
     * 解析gsyn Box payload
     *
     * 与Windows版SyncConfig.decode对齐（struct.unpack_from('>BiBfBBBB', ...)）：
     *   sync_mode(1B) + sync_offset(4B) + interpolation(1B) + video_ratio(4B) +
     *   map_style(1B) + show_trajectory(1B) + show_poi(1B) + default_view(1B)
     */
    private fun parseGsynPayload(payload: ByteArray): SyncRules {
        if (payload.size < 14) return SyncRules()
        val buf = ByteBuffer.wrap(payload).order(ByteOrder.BIG_ENDIAN)
        return SyncRules(
            syncMode = buf.readUInt8(),
            syncOffsetMs = buf.readInt32(),
            interpolation = buf.readUInt8(),
            videoRatio = buf.readFloat32(),
            mapStyle = buf.readUInt8(),
            showTrajectory = buf.readUInt8() != 0,
            showPoi = buf.readUInt8() != 0,
            defaultView = buf.readUInt8()
        )
    }

    /**
     * 获取指定时间戳的GPS位置（含插值）
     * @param timestampMs 毫秒时间戳
     * @return 插值后的GPS坐标 (latitude, longitude) 或 null
     */
    fun getGpsAtTime(timestampMs: Long): Pair<Double, Double>? {
        if (gpsSamples.isEmpty()) return null
        if (gpsSamples.size == 1) return Pair(gpsSamples[0].latitude, gpsSamples[0].longitude)

        // 在采样点中二分查找
        val adjustedTime = timestampMs + syncRules.syncOffsetMs

        // 早于第一个采样点
        if (adjustedTime <= gpsSamples.first().timestampMs) {
            return Pair(gpsSamples.first().latitude, gpsSamples.first().longitude)
        }
        // 晚于最后一个采样点
        if (adjustedTime >= gpsSamples.last().timestampMs) {
            return Pair(gpsSamples.last().latitude, gpsSamples.last().longitude)
        }

        // 二分查找
        var lo = 0
        var hi = gpsSamples.size - 1
        while (lo < hi - 1) {
            val mid = (lo + hi) / 2
            when {
                gpsSamples[mid].timestampMs < adjustedTime -> lo = mid
                gpsSamples[mid].timestampMs > adjustedTime -> hi = mid
                else -> return Pair(gpsSamples[mid].latitude, gpsSamples[mid].longitude)
            }
        }

        val before = gpsSamples[lo]
        val after = gpsSamples[hi]
        val timeRange = after.timestampMs - before.timestampMs
        if (timeRange == 0L) return Pair(before.latitude, before.longitude)

        // 根据插值模式
        return when (syncRules.interpolation) {
            0 -> {
                // 最近邻
                if (adjustedTime - before.timestampMs < after.timestampMs - adjustedTime) {
                    Pair(before.latitude, before.longitude)
                } else {
                    Pair(after.latitude, after.longitude)
                }
            }
            else -> {
                // 线性插值
                val t = (adjustedTime - before.timestampMs).toDouble() / timeRange
                val lat = before.latitude + (after.latitude - before.latitude) * t
                val lon = before.longitude + (after.longitude - before.longitude) * t
                Pair(lat, lon)
            }
        }
    }

    /**
     * 查找距离指定坐标最近的采样点的时间戳
     * @param lat 纬度
     * @param lon 经度
     * @return 最近采样点的时间戳(毫秒) 或 null
     */
    fun getNearestTimestamp(lat: Double, lon: Double): Long? {
        if (gpsSamples.isEmpty()) return null
        var minDist = Double.MAX_VALUE
        var nearestTime = 0L
        for (s in gpsSamples) {
            val dLat = s.latitude - lat
            val dLon = s.longitude - lon
            val dist = dLat * dLat + dLon * dLon
            if (dist < minDist) {
                minDist = dist
                nearestTime = s.timestampMs
            }
        }
        return nearestTime - syncRules.syncOffsetMs
    }

    /**
     * 获取轨迹总距离（公里）
     */
    fun getTotalDistance(): Double {
        if (gpsSamples.size < 2) return 0.0
        var total = 0.0
        for (i in 1 until gpsSamples.size) {
            val a = gpsSamples[i - 1]
            val b = gpsSamples[i]
            total += haversineKm(a.latitude, a.longitude, b.latitude, b.longitude)
        }
        return total
    }

    /**
     * 获取最大速度
     */
    fun getMaxSpeed(): Double {
        return gpsSamples.maxOfOrNull { it.speedKmh } ?: 0.0
    }

    private fun haversineKm(lat1: Double, lon1: Double, lat2: Double, lon2: Double): Double {
        val r = 6371.0 // 地球半径 km
        val dLat = Math.toRadians(lat2 - lat1)
        val dLon = Math.toRadians(lon2 - lon1)
        val a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
                Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2)) *
                Math.sin(dLon / 2) * Math.sin(dLon / 2)
        val c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
        return r * c
    }
}
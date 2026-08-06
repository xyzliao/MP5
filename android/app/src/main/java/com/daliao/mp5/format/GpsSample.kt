package com.daliao.mp5.format

/**
 * GPS采样点 — 对应gloc Box中的每条记录
 *
 * 经纬度使用整数×10^7存储，避免IEEE 754浮点精度问题。
 * 例如：北纬39.9042° → 399042000
 *
 * @param timestampMs 毫秒时间戳，相对于mvhd的时间起点
 * @param latitudeE7 纬度 ×10^7 (WGS84)
 * @param longitudeE7 经度 ×10^7 (WGS84)
 * @param altitudeDm 海拔高度 ×10 (分米，精确到0.1米)
 * @param accuracyM 定位精度，米
 * @param headingDeg 方向角 0-360°，0=正北
 * @param speedKmhX10 速度 km/h ×10 (精确到0.1km/h)
 * @param isPoi 是否为POI标记点
 * @param poiLabel POI标签（可选）
 */
data class GpsSample(
    val timestampMs: Long,
    val latitudeE7: Long,
    val longitudeE7: Long,
    val altitudeDm: Int,
    val accuracyM: Int,
    val headingDeg: Int,
    val speedKmhX10: Int,
    val isPoi: Boolean = false,
    val poiLabel: String? = null
) {
    val latitude: Double get() = latitudeE7 / 10_000_000.0
    val longitude: Double get() = longitudeE7 / 10_000_000.0
    val altitudeM: Double get() = altitudeDm / 10.0
    val speedKmh: Double get() = speedKmhX10 / 10.0

    companion object {
        fun fromDegrees(
            timestampMs: Long,
            latitude: Double,
            longitude: Double,
            altitudeM: Double,
            accuracyM: Int,
            headingDeg: Int,
            speedKmh: Double
        ): GpsSample = GpsSample(
            timestampMs = timestampMs,
            latitudeE7 = (latitude * 10_000_000).toLong(),
            longitudeE7 = (longitude * 10_000_000).toLong(),
            altitudeDm = (altitudeM * 10).toInt(),
            accuracyM = accuracyM,
            headingDeg = headingDeg,
            speedKmhX10 = (speedKmh * 10).toInt()
        )
    }
}
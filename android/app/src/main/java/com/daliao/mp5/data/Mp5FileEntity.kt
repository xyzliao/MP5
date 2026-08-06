package com.daliao.mp5.data

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * MP5文件记录 — 存储在Room数据库中
 */
@Entity(tableName = "mp5_files")
data class Mp5FileEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val filePath: String,         // 文件路径
    val fileName: String,         // 文件名
    val fileSize: Long,           // 文件大小（字节）
    val durationMs: Long,         // 视频时长（毫秒）
    val createdAt: Long,          // 创建时间戳
    val thumbnailPath: String? = null,  // 缩略图路径
    val startLat: Double = 0.0,   // 起点纬度
    val startLon: Double = 0.0,   // 起点经度
    val endLat: Double = 0.0,     // 终点纬度
    val endLon: Double = 0.0,     // 终点经度
    val totalDistanceKm: Double = 0.0,  // 总距离
    val maxSpeedKmh: Double = 0.0,      // 最大速度
    val gpsPointCount: Int = 0,         // GPS采样点数
    val hasMapData: Boolean = false     // 是否包含离线地图数据
)
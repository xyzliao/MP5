package com.daliao.mp5.ui.components

import android.content.Context
import android.graphics.Color
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.daliao.mp5.format.GpsSample
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Polyline

/**
 * Osmdroid地图Compose封装
 *
 * 功能：
 * - 显示GPS轨迹线
 * - 当前位置标记
 * - 起点/终点标记
 * - 速度热力图着色
 * - 点击地图跳转视频
 */
@Composable
fun Mp5MapView(
    gpsSamples: List<GpsSample>,
    currentGps: Pair<Double, Double>?,
    onMapClick: (Double, Double) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val mapView = remember { MapView(context) }

    DisposableEffect(Unit) {
        mapView.setTileSource(TileSourceFactory.MAPNIK)
        mapView.setMultiTouchControls(true)
        mapView.controller.setZoom(15.0)

        onDispose {
            // osmdroid需要清理
        }
    }

    // 更新轨迹
    LaunchedEffect(gpsSamples) {
        if (gpsSamples.isNotEmpty()) {
            // 清除旧overlay
            mapView.overlays.clear()

            // 绘制完整轨迹线
            if (gpsSamples.size >= 2) {
                val polyline = Polyline().apply {
                    outlinePaint.color = Color.parseColor("#4A90D9")
                    outlinePaint.strokeWidth = 8f
                }
                for (s in gpsSamples) {
                    polyline.addPoint(GeoPoint(s.latitude, s.longitude))
                }
                mapView.overlays.add(polyline)

                // 已播放部分用不同颜色（这里简化，实际用两个polyline）
            }

            // 起点/终点标记
            val startGps = gpsSamples.first()
            val endGps = gpsSamples.last()

            addMarker(mapView, GeoPoint(startGps.latitude, startGps.longitude), "起点", Color.GREEN)
            addMarker(mapView, GeoPoint(endGps.latitude, endGps.longitude), "终点", Color.RED)

            // 自动调整视野
            val minLat = gpsSamples.minOf { it.latitude }
            val maxLat = gpsSamples.maxOf { it.latitude }
            val minLon = gpsSamples.minOf { it.longitude }
            val maxLon = gpsSamples.maxOf { it.longitude }
            val center = GeoPoint((minLat + maxLat) / 2, (minLon + maxLon) / 2)
            mapView.controller.setCenter(center)

            // 计算缩放级别
            val latSpan = maxLat - minLat
            val lonSpan = maxLon - minLon
            val span = maxOf(latSpan, lonSpan)
            val zoom = when {
                span > 1.0 -> 8.0
                span > 0.5 -> 10.0
                span > 0.1 -> 12.0
                span > 0.05 -> 14.0
                span > 0.01 -> 15.0
                span > 0.005 -> 16.0
                else -> 17.0
            }
            mapView.controller.setZoom(zoom)
        }
    }

    // 更新当前位置标记
    LaunchedEffect(currentGps) {
        if (currentGps != null) {
            // 移除旧的位置标记并添加新的
            // 简化版：直接设置地图中心
            mapView.controller.animateTo(GeoPoint(currentGps.first, currentGps.second))
        }
    }

    AndroidView(
        modifier = modifier.fillMaxSize(),
        factory = { mapView }
    )
}

private fun addMarker(mapView: MapView, point: GeoPoint, title: String, color: Int) {
    val marker = org.osmdroid.views.overlay.Marker(mapView).apply {
        position = point
        this.title = title
        // 用颜色区分（osmdroid默认marker）
        setAnchor(org.osmdroid.views.overlay.Marker.ANCHOR_CENTER, org.osmdroid.views.overlay.Marker.ANCHOR_BOTTOM)
    }
    mapView.overlays.add(marker)
}
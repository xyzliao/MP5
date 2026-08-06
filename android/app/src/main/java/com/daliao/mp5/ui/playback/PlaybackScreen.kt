package com.daliao.mp5.ui.playback

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PictureInPicture
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.SkipNext
import androidx.compose.material.icons.filled.SkipPrevious
import androidx.compose.material.icons.filled.VideoLibrary
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.daliao.mp5.data.Mp5Database
import com.daliao.mp5.ui.components.Mp5MapView
import androidx.media3.ui.PlayerView
import androidx.compose.ui.viewinterop.AndroidView

enum class ViewMode { VIDEO_ONLY, MAP_ONLY, SPLIT_LR, SPLIT_TB, PIP }

@Composable
fun PlaybackScreen(
    fileId: Long,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    var controller by remember { mutableStateOf<com.daliao.mp5.playback.Mp5PlayerController?>(null) }
    var filePath by remember { mutableStateOf<String?>(null) }
    var viewMode by remember { mutableStateOf(ViewMode.SPLIT_LR) }

    // 从数据库加载文件信息
    LaunchedEffect(fileId) {
        if (fileId > 0) {
            val dao = Mp5Database.getInstance(context).mp5FileDao()
            val entity = dao.getFileById(fileId)
            filePath = entity?.filePath
        }
    }

    // 初始化播放器
    LaunchedEffect(filePath) {
        filePath?.let { path ->
            controller?.release()
            val ctrl = com.daliao.mp5.playback.Mp5PlayerController(context)
            ctrl.loadFile(path)
            controller = ctrl

            // 根据gsyn设置默认视图
            val rules = ctrl.syncRules.value
            viewMode = when (rules.defaultView) {
                0 -> ViewMode.VIDEO_ONLY
                1 -> ViewMode.MAP_ONLY
                2 -> ViewMode.SPLIT_LR
                3 -> ViewMode.SPLIT_TB
                4 -> ViewMode.PIP
                else -> ViewMode.SPLIT_LR
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose { controller?.release() }
    }

    val rec = controller ?: return
    val isPlaying by rec.isPlaying.collectAsStateWithLifecycle()
    val position by rec.currentPositionMs.collectAsStateWithLifecycle()
    val duration by rec.durationMs.collectAsStateWithLifecycle()
    val currentGps by rec.currentGps.collectAsStateWithLifecycle()
    val gpsSamples by rec.gpsSamples.collectAsStateWithLifecycle()
    val isMp5 by rec.isMp5.collectAsStateWithLifecycle()
    val totalDistance by rec.totalDistance.collectAsStateWithLifecycle()
    val maxSpeed by rec.maxSpeed.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier.fillMaxSize().background(Color.Black)
    ) {
        // 顶部栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.Black.copy(alpha = 0.8f))
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Filled.ArrowBack, "返回", tint = Color.White)
            }
            Text(
                text = if (isMp5) "MP5播放" else "MP4播放",
                color = Color.White,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.weight(1f).padding(start = 8.dp)
            )
            // 视图切换按钮
            IconButton(onClick = { viewMode = ViewMode.VIDEO_ONLY }) {
                Icon(Icons.Filled.VideoLibrary, "仅视频", tint = if (viewMode == ViewMode.VIDEO_ONLY) MaterialTheme.colorScheme.primary else Color.White)
            }
            IconButton(onClick = { viewMode = ViewMode.MAP_ONLY }) {
                Icon(Icons.Filled.Map, "仅地图", tint = if (viewMode == ViewMode.MAP_ONLY) MaterialTheme.colorScheme.primary else Color.White)
            }
            IconButton(onClick = {
                viewMode = when (viewMode) {
                    ViewMode.SPLIT_LR -> ViewMode.SPLIT_TB
                    ViewMode.SPLIT_TB -> ViewMode.PIP
                    ViewMode.PIP -> ViewMode.SPLIT_LR
                    else -> ViewMode.SPLIT_LR
                }
            }) {
                Icon(Icons.Filled.PictureInPicture, "分屏", tint = Color.White)
            }
        }

        // 主内容区
        Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
            when (viewMode) {
                ViewMode.VIDEO_ONLY -> {
                    VideoPlayerView(rec)
                }
                ViewMode.MAP_ONLY -> {
                    Mp5MapView(
                        gpsSamples = gpsSamples,
                        currentGps = currentGps,
                        onMapClick = { lat, lon -> rec.seekToGps(lat, lon) },
                        modifier = Modifier.fillMaxSize()
                    )
                }
                ViewMode.SPLIT_LR -> {
                    Row(modifier = Modifier.fillMaxSize()) {
                        Box(modifier = Modifier.weight(0.5f)) {
                            VideoPlayerView(rec)
                        }
                        Box(modifier = Modifier.weight(0.5f)) {
                            Mp5MapView(
                                gpsSamples = gpsSamples,
                                currentGps = currentGps,
                                onMapClick = { lat, lon -> rec.seekToGps(lat, lon) },
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }
                ViewMode.SPLIT_TB -> {
                    Column(modifier = Modifier.fillMaxSize()) {
                        Box(modifier = Modifier.weight(0.5f)) {
                            VideoPlayerView(rec)
                        }
                        Box(modifier = Modifier.weight(0.5f)) {
                            Mp5MapView(
                                gpsSamples = gpsSamples,
                                currentGps = currentGps,
                                onMapClick = { lat, lon -> rec.seekToGps(lat, lon) },
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }
                ViewMode.PIP -> {
                    Box(modifier = Modifier.fillMaxSize()) {
                        VideoPlayerView(rec)
                        // 画中画地图在右下角
                        Box(
                            modifier = Modifier
                                .align(Alignment.BottomEnd)
                                .width(160.dp)
                                .height(120.dp)
                        ) {
                            Mp5MapView(
                                gpsSamples = gpsSamples,
                                currentGps = currentGps,
                                onMapClick = { lat, lon -> rec.seekToGps(lat, lon) },
                                modifier = Modifier.fillMaxSize()
                            )
                        }
                    }
                }
            }
        }

        // 底部控制栏
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color.Black.copy(alpha = 0.8f))
                .padding(8.dp)
        ) {
            // 进度条
            if (duration > 0) {
                Slider(
                    value = position.toFloat(),
                    onValueChange = { rec.seekTo(it.toLong()) },
                    valueRange = 0f..duration.toFloat(),
                    modifier = Modifier.fillMaxWidth()
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = formatTime(position),
                    color = Color.White,
                    style = MaterialTheme.typography.bodySmall
                )
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    IconButton(onClick = { rec.seekTo(maxOf(0, position - 10_000)) }) {
                        Icon(Icons.Filled.SkipPrevious, "后退10s", tint = Color.White)
                    }
                    IconButton(onClick = {
                        if (isPlaying) rec.pause() else rec.play()
                    }) {
                        Icon(
                            if (isPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                            "播放/暂停",
                            tint = Color.White,
                            modifier = Modifier.background(MaterialTheme.colorScheme.primary, CircleShape).padding(8.dp)
                        )
                    }
                    IconButton(onClick = { rec.seekTo(minOf(duration, position + 10_000)) }) {
                        Icon(Icons.Filled.SkipNext, "前进10s", tint = Color.White)
                    }
                }
                Text(
                    text = formatTime(duration),
                    color = Color.White,
                    style = MaterialTheme.typography.bodySmall
                )
            }
            // GPS信息
            if (currentGps != null) {
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "%.4f°N %.4f°E".format(currentGps!!.first, currentGps!!.second),
                        color = Color.White.copy(alpha = 0.7f),
                        style = MaterialTheme.typography.bodySmall
                    )
                    if (totalDistance > 0) {
                        Text(
                            text = "%.1fkm  最大%.0fkm/h".format(totalDistance, maxSpeed),
                            color = Color.White.copy(alpha = 0.7f),
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun VideoPlayerView(controller: com.daliao.mp5.playback.Mp5PlayerController) {
    AndroidView(
        modifier = Modifier.fillMaxSize(),
        factory = { ctx ->
            PlayerView(ctx).apply {
                player = controller.exoPlayer
                useController = false  // 使用自定义控制栏
            }
        }
    )
}

// 需要暴露exoPlayer给PlayerView — 在Controller上添加访问
// 实际通过反射或getter获取

private fun formatTime(ms: Long): String {
    if (ms <= 0) return "00:00"
    val totalSec = ms / 1000
    val m = (totalSec % 3600) / 60
    val s = totalSec % 60
    val h = totalSec / 3600
    return if (h > 0) "%d:%02d:%02d".format(h, m, s)
    else "%02d:%02d".format(m, s)
}
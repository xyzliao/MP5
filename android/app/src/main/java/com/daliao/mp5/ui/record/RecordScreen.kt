package com.daliao.mp5.ui.record

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.Recorder
import androidx.camera.video.VideoCapture
import androidx.camera.view.PreviewView
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FiberManualRecord
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.PushPin
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.daliao.mp5.recording.Mp5Recorder
import java.util.concurrent.Executors

@Composable
fun RecordScreen(
    onFinished: (Long?) -> Unit,
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var hasPermissions by remember { mutableStateOf(false) }
    var recorder by remember { mutableStateOf<Mp5Recorder?>(null) }
    var previewView by remember { mutableStateOf<PreviewView?>(null) }
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }

    // 权限请求
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result ->
        hasPermissions = result.values.all { it }
    }

    LaunchedEffect(Unit) {
        val permissions = arrayOf(
            Manifest.permission.CAMERA,
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION
        )
        val allGranted = permissions.all {
            ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED
        }
        if (allGranted) {
            hasPermissions = true
        } else {
            permissionLauncher.launch(permissions)
        }
    }

    // 初始化Recorder
    LaunchedEffect(hasPermissions) {
        if (hasPermissions && recorder == null) {
            recorder = Mp5Recorder(context)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            cameraExecutor.shutdown()
            recorder?.stop()
        }
    }

    if (!hasPermissions) {
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text("需要摄像头和定位权限", style = MaterialTheme.typography.bodyLarge)
                Spacer(modifier = Modifier.height(16.dp))
                Button(onClick = {
                    permissionLauncher.launch(arrayOf(
                        Manifest.permission.CAMERA,
                        Manifest.permission.RECORD_AUDIO,
                        Manifest.permission.ACCESS_FINE_LOCATION,
                        Manifest.permission.ACCESS_COARSE_LOCATION
                    ))
                }) {
                    Text("授予权限")
                }
            }
        }
        return
    }

    val rec = recorder ?: return
    val state by rec.state.collectAsStateWithLifecycle()
    val elapsed by rec.elapsedMs.collectAsStateWithLifecycle()
    val gpsLocation by rec.currentLocation.collectAsStateWithLifecycle()
    val gpsCount by rec.gpsSampleCount.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier.fillMaxSize().background(Color.Black)
    ) {
        // 视频预览（占大部分空间）
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(Color.Black)
        ) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    PreviewView(ctx).also { pv ->
                        previewView = pv
                        startCamera(ctx, pv, rec, lifecycleOwner, cameraExecutor)
                    }
                }
            )

            // 顶部状态栏覆盖层
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(12.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // 录制状态
                if (state == Mp5Recorder.State.RECORDING) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Filled.FiberManualRecord,
                            contentDescription = "录制中",
                            tint = Color.Red,
                            modifier = Modifier.size(16.dp)
                        )
                        Text(
                            text = formatTime(elapsed),
                            color = Color.White,
                            modifier = Modifier.padding(start = 4.dp),
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                // GPS状态
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Filled.LocationOn,
                        contentDescription = "GPS",
                        tint = if (gpsLocation != null) Color.Green else Color.Gray,
                        modifier = Modifier.size(16.dp)
                    )
                    Text(
                        text = "$gpsCount",
                        color = Color.White,
                        modifier = Modifier.padding(start = 4.dp),
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            // 底部GPS信息覆盖层
            if (gpsLocation != null) {
                Card(
                    modifier = Modifier
                        .align(Alignment.BottomStart)
                        .padding(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = Color.Black.copy(alpha = 0.6f)
                    )
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text(
                            text = "%.4f°N %.4f°E".format(
                                gpsLocation!!.latitude,
                                gpsLocation!!.longitude
                            ),
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            text = "%.0f km/h  %dm".format(
                                gpsLocation!!.speedKmh,
                                gpsLocation!!.altitudeM
                            ),
                            color = Color.White,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }

        // 控制栏
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(80.dp)
                .background(Color.Black)
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically
        ) {
            when (state) {
                Mp5Recorder.State.IDLE -> {
                    // 录制按钮
                    IconButton(
                        onClick = { rec.start() },
                        modifier = Modifier.size(64.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .background(Color.Red, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(48.dp)
                                    .background(Color.White, CircleShape)
                            )
                        }
                    }
                }
                Mp5Recorder.State.RECORDING -> {
                    // 暂停
                    IconButton(
                        onClick = { rec.pause() },
                        modifier = Modifier.size(56.dp)
                    ) {
                        Icon(
                            Icons.Filled.Pause,
                            contentDescription = "暂停",
                            tint = Color.White,
                            modifier = Modifier.size(48.dp)
                        )
                    }
                    // POI标记
                    IconButton(
                        onClick = { rec.addPoi() },
                        modifier = Modifier.size(56.dp)
                    ) {
                        Icon(
                            Icons.Filled.PushPin,
                            contentDescription = "标记POI",
                            tint = MaterialTheme.colorScheme.secondary,
                            modifier = Modifier.size(40.dp)
                        )
                    }
                    // 停止
                    IconButton(
                        onClick = {
                            rec.stop()
                            // 等待完成后回调
                        },
                        modifier = Modifier.size(64.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .background(Color.Red, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(24.dp)
                                    .background(Color.White)
                            )
                        }
                    }
                }
                Mp5Recorder.State.PAUSED -> {
                    // 继续录制
                    IconButton(
                        onClick = { rec.resume() },
                        modifier = Modifier.size(56.dp)
                    ) {
                        Icon(
                            Icons.Filled.PlayArrow,
                            contentDescription = "继续",
                            tint = Color.White,
                            modifier = Modifier.size(48.dp)
                        )
                    }
                    // 停止
                    IconButton(
                        onClick = { rec.stop() },
                        modifier = Modifier.size(64.dp)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(64.dp)
                                .background(Color.Red, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(24.dp)
                                    .background(Color.White)
                            )
                        }
                    }
                }
                Mp5Recorder.State.FINALIZING -> {
                    Text(
                        "正在封装MP5...",
                        color = Color.White,
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }
        }

        // 完成后跳转
        LaunchedEffect(state) {
            if (state == Mp5Recorder.State.IDLE && rec.lastInsertedId != null) {
                val id = rec.lastInsertedId
                rec.lastInsertedId = null
                onFinished(id)
            }
        }
    }
}

private fun startCamera(
    context: android.content.Context,
    previewView: PreviewView,
    recorder: Mp5Recorder,
    lifecycleOwner: androidx.lifecycle.LifecycleOwner,
    executor: java.util.concurrent.Executor
) {
    val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
    cameraProviderFuture.addListener({
        val cameraProvider = cameraProviderFuture.get()

        val preview = Preview.Builder().build().also {
            it.setSurfaceProvider(previewView.surfaceProvider)
        }

        val recorderBuilder = Recorder.Builder()
            .setQualitySelector(
                androidx.camera.video.QualitySelector.of(
                    androidx.camera.video.Quality.FHD
                )
            )
        val videoCapture = VideoCapture.withOutput(recorderBuilder.build())

        recorder.setVideoCapture(videoCapture)

        try {
            cameraProvider.unbindAll()
            cameraProvider.bindToLifecycle(
                lifecycleOwner,
                CameraSelector.DEFAULT_BACK_CAMERA,
                preview,
                videoCapture
            )
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }, executor)
}

private fun formatTime(ms: Long): String {
    val totalSec = ms / 1000
    val h = totalSec / 3600
    val m = (totalSec % 3600) / 60
    val s = totalSec % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s)
    else "%02d:%02d".format(m, s)
}
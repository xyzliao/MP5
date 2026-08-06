package com.daliao.mp5.recording

import android.content.Context
import android.net.Uri
import android.util.Log
import androidx.camera.core.CameraSelector
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.Recording
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.core.content.ContextCompat
import androidx.core.util.Consumer
import com.daliao.mp5.data.Mp5Database
import com.daliao.mp5.data.Mp5FileEntity
import com.daliao.mp5.format.Mp5Muxer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * MP5录制器 — 协调CameraX视频录制 + GPS采集 + MP5封装
 *
 * 流程：
 * 1. 启动CameraX VideoCapture录制MP4到临时文件
 * 2. 同时启动GPS采集
 * 3. 停止后：用Mp5Muxer将gloc/gsyn box嵌入MP4 → MP5
 * 4. 在Room数据库中登记文件
 */
class Mp5Recorder(private val context: Context) {

    enum class State { IDLE, RECORDING, PAUSED, FINALIZING }

    private val _state = MutableStateFlow(State.IDLE)
    val state: StateFlow<State> = _state

    private val _elapsedMs = MutableStateFlow(0L)
    val elapsedMs: StateFlow<Long> = _elapsedMs

    private val gpsCollector = GpsCollector(context)
    val currentLocation = gpsCollector.currentLocation
    val gpsSampleCount = gpsCollector.sampleCount

    private var videoCapture: VideoCapture<Recorder>? = null
    private var recording: Recording? = null
    private var startTimeMs: Long = 0
    private var tempMp4File: File? = null
    private var pendingGpsSamples: List<com.daliao.mp5.format.GpsSample> = emptyList()

    fun setVideoCapture(capture: VideoCapture<Recorder>) {
        videoCapture = capture
    }

    fun start() {
        if (_state.value != State.IDLE && _state.value != State.PAUSED) return

        if (_state.value == State.PAUSED) {
            // 续录
            _state.value = State.RECORDING
            return
        }

        startTimeMs = System.currentTimeMillis()
        _elapsedMs.value = 0L

        // 创建临时MP4文件
        val outputDir = File(context.filesDir, "mp5").apply { mkdirs() }
        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        tempMp4File = File(outputDir, "temp_${timestamp}.mp4")

        // 启动GPS采集
        gpsCollector.start(sampleRateHz = 1, startTimeMs = startTimeMs)

        // 启动CameraX录制
        val recorder = videoCapture?.output?.let {
            Recorder.Builder()
                .setQualitySelector(QualitySelector.of(Quality.FHD))
                .build()
        }

        if (recorder == null) {
            Log.e("Mp5Recorder", "No video capture available")
            return
        }

        val outputOptions = FileOutputOptions.Builder(tempMp4File!!).build()

        recording = recorder.startRecording(
            outputOptions,
            ContextCompat.getMainExecutor(context),
            object : Consumer<VideoRecordEvent> {
                override fun accept(event: VideoRecordEvent) {
                    when (event) {
                        is VideoRecordEvent.Status -> {
                            _elapsedMs.value = System.currentTimeMillis() - startTimeMs
                        }
                        is VideoRecordEvent.Start -> {
                            _state.value = State.RECORDING
                        }
                        is VideoRecordEvent.Finalize -> {
                            if (event.hasError()) {
                                Log.e("Mp5Recorder", "Recording error: ${event.error}")
                                _state.value = State.IDLE
                            } else {
                                finalizeMp5()
                            }
                        }
                        is VideoRecordEvent.Pause -> {
                            _state.value = State.PAUSED
                        }
                        is VideoRecordEvent.Resume -> {
                            _state.value = State.RECORDING
                        }
                    }
                }
            }
        )
        _state.value = State.RECORDING
    }

    fun pause() {
        recording?.pause()
        _state.value = State.PAUSED
    }

    fun resume() {
        recording?.resume()
        _state.value = State.RECORDING
    }

    fun stop() {
        _state.value = State.FINALIZING
        pendingGpsSamples = gpsCollector.stop()
        recording?.stop()
    }

    private fun finalizeMp5() {
        Thread {
            try {
                val mp4 = tempMp4File ?: return@Thread
                val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
                val mp5File = File(File(context.filesDir, "mp5").apply { mkdirs() }, "MP5_${timestamp}.mp5")

                // 用Mp5Muxer将GPS数据嵌入MP4
                val muxer = Mp5Muxer()
                muxer.addGpsSamples(pendingGpsSamples)
                muxer.mux(mp4, mp5File)

                // 删除临时MP4
                mp4.delete()

                // 写入数据库
                val db = Mp5Database.getInstance(context)
                val dao = db.mp5FileDao()

                val firstGps = pendingGpsSamples.firstOrNull()
                val lastGps = pendingGpsSamples.lastOrNull()

                val entity = Mp5FileEntity(
                    filePath = mp5File.absolutePath,
                    fileName = mp5File.name,
                    fileSize = mp5File.length(),
                    durationMs = _elapsedMs.value,
                    createdAt = System.currentTimeMillis(),
                    startLat = firstGps?.latitude ?: 0.0,
                    startLon = firstGps?.longitude ?: 0.0,
                    endLat = lastGps?.latitude ?: 0.0,
                    endLon = lastGps?.longitude ?: 0.0,
                    gpsPointCount = pendingGpsSamples.size,
                    hasMapData = false
                )

                val id = dao.insert(entity)
                _state.value = State.IDLE
                lastInsertedId = id

            } catch (e: Exception) {
                Log.e("Mp5Recorder", "Finalize error", e)
                _state.value = State.IDLE
            }
        }.start()
    }

    var lastInsertedId: Long? = null
        private set

    fun addPoi(label: String? = null) {
        gpsCollector.addPoi(label)
    }
}
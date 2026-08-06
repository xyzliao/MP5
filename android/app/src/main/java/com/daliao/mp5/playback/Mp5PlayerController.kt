package com.daliao.mp5.playback

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.daliao.mp5.format.Mp5Parser
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.File

/**
 * MP5播放控制器 — 管理ExoPlayer视频播放 + GPS同步
 *
 * 视频→地图：播放位置变化时，查询gloc获取GPS坐标
 * 地图→视频：地图点击时，查找最近GPS点的时间戳，seek视频
 */
class Mp5PlayerController(private val context: Context) {

    var exoPlayer: ExoPlayer? = null
        private set
    private var mp5Parser: Mp5Parser? = null

    private val _currentPositionMs = MutableStateFlow(0L)
    val currentPositionMs: StateFlow<Long> = _currentPositionMs

    private val _durationMs = MutableStateFlow(0L)
    val durationMs: StateFlow<Long> = _durationMs

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying

    private val _currentGps = MutableStateFlow<Pair<Double, Double>?>(null)
    val currentGps: StateFlow<Pair<Double, Double>?> = _currentGps

    private val _gpsSamples = MutableStateFlow<List<com.daliao.mp5.format.GpsSample>>(emptyList())
    val gpsSamples: StateFlow<List<com.daliao.mp5.format.GpsSample>> = _gpsSamples

    private val _syncRules = MutableStateFlow(Mp5Parser.SyncRules())
    val syncRules: StateFlow<Mp5Parser.SyncRules> = _syncRules

    private val _isMp5 = MutableStateFlow(false)
    val isMp5: StateFlow<Boolean> = _isMp5

    private val _totalDistance = MutableStateFlow(0.0)
    val totalDistance: StateFlow<Double> = _totalDistance

    private val _maxSpeed = MutableStateFlow(0.0)
    val maxSpeed: StateFlow<Double> = _maxSpeed

    fun loadFile(filePath: String) {
        val file = File(filePath)
        if (!file.exists()) return

        // 解析MP5
        val parser = Mp5Parser(file)
        parser.parse()
        mp5Parser = parser

        _gpsSamples.value = parser.gpsSamples
        _syncRules.value = parser.syncRules
        _isMp5.value = parser.isMp5
        _totalDistance.value = parser.getTotalDistance()
        _maxSpeed.value = parser.getMaxSpeed()

        // 初始化ExoPlayer
        exoPlayer = ExoPlayer.Builder(context).build().also { player ->
            player.setMediaItem(MediaItem.fromUri(file.absolutePath))
            player.prepare()
            player.addListener(object : Player.Listener {
                override fun onIsPlayingChanged(playing: Boolean) {
                    _isPlaying.value = playing
                }
            })
        }

        // 启动位置轮询
        startPolling()
    }

    private fun startPolling() {
        exoPlayer?.let { player ->
            Thread {
                while (true) {
                    try {
                        val pos = player.currentPosition
                        val dur = player.duration
                        _currentPositionMs.value = pos
                        if (dur > 0) _durationMs.value = dur

                        // 查询当前GPS位置
                        if (mp5Parser != null && mp5Parser!!.gpsSamples.isNotEmpty()) {
                            _currentGps.value = mp5Parser!!.getGpsAtTime(pos)
                        }

                        Thread.sleep(50) // 20fps更新
                    } catch (e: Exception) {
                        break
                    }
                }
            }.start()
        }
    }

    fun play() { exoPlayer?.play() }
    fun pause() { exoPlayer?.pause() }
    fun seekTo(ms: Long) { exoPlayer?.seekTo(ms) }

    /** 地图→视频：点击地图坐标，跳转到对应视频时间 */
    fun seekToGps(lat: Double, lon: Double) {
        mp5Parser?.getNearestTimestamp(lat, lon)?.let { timestamp ->
            seekTo(timestamp)
        }
    }

    fun release() {
        exoPlayer?.release()
        exoPlayer = null
    }
}
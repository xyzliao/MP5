package com.daliao.mp5.recording

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import androidx.core.content.ContextCompat
import com.daliao.mp5.format.GpsSample
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * GPS采集器 — 使用FusedLocationProvider获取GPS坐标
 *
 * 采样率可配置：1Hz（步行）、5Hz（驾车）、10Hz（高速运动）
 * 提供实时位置状态Flow供UI订阅
 */
class GpsCollector(private val context: Context) {

    private val fusedClient: FusedLocationProviderClient =
        LocationServices.getFusedLocationProviderClient(context)

    private val _currentLocation = MutableStateFlow<GpsSample?>(null)
    val currentLocation: StateFlow<GpsSample?> = _currentLocation

    private val _sampleCount = MutableStateFlow(0)
    val sampleCount: StateFlow<Int> = _sampleCount

    private val samples = mutableListOf<GpsSample>()
    private var startTimeMs: Long = 0
    private var locationCallback: LocationCallback? = null

    var sampleRateHz: Int = 1
        private set

    fun hasPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context, Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun start(sampleRateHz: Int = 1, startTimeMs: Long = System.currentTimeMillis()) {
        this.sampleRateHz = sampleRateHz
        this.startTimeMs = startTimeMs
        samples.clear()
        _sampleCount.value = 0

        if (!hasPermission()) return

        val intervalMs = (1000 / sampleRateHz).toLong()

        val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, intervalMs)
            .setMinUpdateIntervalMillis(intervalMs / 2)
            .setMaxUpdateDelayMillis(intervalMs * 2)
            .build()

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { loc -> onLocation(loc) }
            }
        }

        fusedClient.requestLocationUpdates(request, locationCallback!!, context.mainLooper)
    }

    private fun onLocation(location: Location) {
        val timestamp = System.currentTimeMillis() - startTimeMs
        val sample = GpsSample.fromDegrees(
            timestampMs = timestamp,
            latitude = location.latitude,
            longitude = location.longitude,
            altitudeM = if (location.hasAltitude()) location.altitude else 0.0,
            accuracyM = if (location.hasAccuracy()) location.accuracy.toInt() else 0,
            headingDeg = if (location.hasBearing()) location.bearing.toInt() else 0,
            speedKmh = if (location.hasSpeed()) location.speed * 3.6 else 0.0
        )
        samples.add(sample)
        _currentLocation.value = sample
        _sampleCount.value = samples.size
    }

    fun stop(): List<GpsSample> {
        locationCallback?.let { fusedClient.removeLocationUpdates(it) }
        locationCallback = null
        return ArrayList(samples)
    }

    fun getCurrentSamples(): List<GpsSample> = ArrayList(samples)

    fun addPoi(label: String? = null) {
        val current = _currentLocation.value ?: return
        samples.add(current.copy(isPoi = true, poiLabel = label))
        _sampleCount.value = samples.size
    }
}
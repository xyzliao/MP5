package com.daliao.mp5

import android.app.Application
import org.osmdroid.config.Configuration

/**
 * MP5 Application — 全局应用配置
 *
 * @author 大米斗（Aniseedaliao）
 */
class MP5App : Application() {
    override fun onCreate() {
        super.onCreate()
        // Osmdroid配置
        Configuration.getInstance().userAgentValue = "MP5Recorder/0.1"
        Configuration.getInstance().osmdroidBasePath = filesDir
        Configuration.getInstance().osmdroidTileCache = cacheDir
    }
}
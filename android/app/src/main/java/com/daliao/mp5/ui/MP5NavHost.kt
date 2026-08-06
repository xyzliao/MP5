package com.daliao.mp5.ui

import androidx.compose.runtime.Composable
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.daliao.mp5.ui.files.FileListScreen
import com.daliao.mp5.ui.playback.PlaybackScreen
import com.daliao.mp5.ui.record.RecordScreen

object Routes {
    const val FILES = "files"
    const val RECORD = "record"
    const val PLAYBACK = "playback/{fileId}"

    fun playback(fileId: Long) = "playback/$fileId"
}

@Composable
fun MP5NavHost() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.FILES) {
        composable(Routes.FILES) {
            FileListScreen(
                onRecordClick = { navController.navigate(Routes.RECORD) },
                onFileClick = { fileId -> navController.navigate(Routes.playback(fileId)) }
            )
        }
        composable(Routes.RECORD) {
            RecordScreen(
                onFinished = { fileId ->
                    navController.popBackStack()
                    if (fileId != null) {
                        navController.navigate(Routes.playback(fileId))
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }
        composable(Routes.PLAYBACK) { backStackEntry ->
            val fileId = backStackEntry.arguments?.getString("fileId")?.toLongOrNull() ?: -1L
            PlaybackScreen(
                fileId = fileId,
                onBack = { navController.popBackStack() }
            )
        }
    }
}
package com.daliao.mp5.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF1A73E8),
    onPrimary = Color.White,
    secondary = Color(0xFF34A853),
    onSecondary = Color.White,
    tertiary = Color(0xFFEA4335),
    background = Color(0xFFF8F9FA),
    surface = Color.White,
)

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFF8AB4F8),
    onPrimary = Color(0xFF002D6B),
    secondary = Color(0xFF81C995),
    onSecondary = Color(0xFF00390D),
    tertiary = Color(0xFFF28B82),
    background = Color(0xFF202124),
    surface = Color(0xFF303134),
)

@Composable
fun MP5Theme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
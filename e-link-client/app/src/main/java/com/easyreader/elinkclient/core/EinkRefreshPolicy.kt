package com.easyreader.elinkclient.core

import android.os.Build

enum class RefreshAction {
    NONE,
    PARTIAL,
    FULL,
}

enum class EinkRefreshMode(
    val label: String,
    val fullRefreshInterval: Int,
) {
    SPEED("Speed", 8),
    BALANCED("Balanced", 5),
    QUALITY("Quality", 3),
}

class EinkRefreshPolicy(
    initialMode: EinkRefreshMode = detectDefaultMode(),
) {
    var mode: EinkRefreshMode = initialMode
        private set

    private var pageTurnCount: Int = 0

    fun cycleMode(): EinkRefreshMode {
        mode = when (mode) {
            EinkRefreshMode.SPEED -> EinkRefreshMode.BALANCED
            EinkRefreshMode.BALANCED -> EinkRefreshMode.QUALITY
            EinkRefreshMode.QUALITY -> EinkRefreshMode.SPEED
        }
        return mode
    }

    fun resetChapter() {
        pageTurnCount = 0
    }

    fun onPageTurn(): RefreshAction {
        pageTurnCount += 1
        return if (pageTurnCount % mode.fullRefreshInterval == 0) {
            RefreshAction.FULL
        } else {
            RefreshAction.PARTIAL
        }
    }

    companion object {
        fun detectDefaultMode(manufacturer: String = Build.MANUFACTURER.orEmpty()): EinkRefreshMode {
            val normalized = manufacturer.lowercase()
            return when {
                normalized.contains("onyx") || normalized.contains("boox") -> EinkRefreshMode.BALANCED
                normalized.contains("hisense") -> EinkRefreshMode.SPEED
                else -> EinkRefreshMode.BALANCED
            }
        }
    }
}

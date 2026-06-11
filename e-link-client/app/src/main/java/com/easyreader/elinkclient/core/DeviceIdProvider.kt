package com.easyreader.elinkclient.core

import android.content.Context
import java.util.UUID

class DeviceIdProvider(private val context: Context) {
    fun getOrCreate(): String {
        val prefs = context.getSharedPreferences(AppConfig.PREFS_NAME, Context.MODE_PRIVATE)
        val existing = prefs.getString(AppConfig.KEY_DEVICE_ID, null)
        if (!existing.isNullOrBlank()) {
            return existing
        }
        val generated = "eink-${UUID.randomUUID()}"
        prefs.edit().putString(AppConfig.KEY_DEVICE_ID, generated).apply()
        return generated
    }
}

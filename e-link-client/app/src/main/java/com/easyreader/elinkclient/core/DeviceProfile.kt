package com.easyreader.elinkclient.core

import android.app.ActivityManager
import android.content.Context

object DeviceProfile {
    fun isLowRamDevice(context: Context): Boolean {
        val manager = context.getSystemService(ActivityManager::class.java) ?: return false
        return manager.isLowRamDevice
    }
}

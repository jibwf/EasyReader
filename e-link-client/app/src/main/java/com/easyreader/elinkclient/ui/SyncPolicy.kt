package com.easyreader.elinkclient.ui

enum class NetworkMode(val label: String) {
    OFFLINE("WiFi 未连接"),
    WIFI_ONLINE("WiFi 已连接"),
}

enum class SyncMode(val storageValue: String, val label: String) {
    MANUAL_PROGRESS_ONLY("manual_only", "仅手动推送进度"),
    AUTO_ON_WIFI("auto_when_online", "WiFi 下自动推送进度");

    companion object {
        fun fromStorage(value: String?): SyncMode {
            return entries.firstOrNull { it.storageValue == value } ?: AUTO_ON_WIFI
        }
    }
}

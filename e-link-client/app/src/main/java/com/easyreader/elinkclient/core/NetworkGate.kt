package com.easyreader.elinkclient.core

import android.content.Context

class NetworkGate(
    private val isWifiOnlineProvider: () -> Boolean,
) {
    constructor(context: Context) : this(
        isWifiOnlineProvider = {
            NetworkStateProvider.isWifiAvailable(context.applicationContext)
        },
    )

    fun canUseNetwork(): Boolean = isWifiOnlineProvider()

    fun requireWifiOnline(operation: String) {
        if (!canUseNetwork()) {
            throw NetworkDisabledException(operation)
        }
    }
}
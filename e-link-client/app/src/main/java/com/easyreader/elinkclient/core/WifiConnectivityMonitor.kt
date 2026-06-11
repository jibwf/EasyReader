package com.easyreader.elinkclient.core

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class WifiConnectivityMonitor(
    private val context: Context,
) {
    private val appContext = context.applicationContext
    private val connectivityManager = appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
    private val _isWifiOnline = MutableStateFlow(NetworkStateProvider.isWifiAvailable(appContext))
    private var started = false

    val isWifiOnline: StateFlow<Boolean> = _isWifiOnline.asStateFlow()

    private val callback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            refresh()
        }

        override fun onLost(network: Network) {
            refresh()
        }

        override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
            refresh()
        }

        override fun onUnavailable() {
            refresh()
        }
    }

    fun start() {
        if (started) {
            refresh()
            return
        }
        started = true
        refresh()
        runCatching {
            connectivityManager?.registerDefaultNetworkCallback(callback)
        }.onFailure {
            refresh()
        }
    }

    fun stop() {
        if (!started) {
            return
        }
        started = false
        runCatching {
            connectivityManager?.unregisterNetworkCallback(callback)
        }
    }

    fun refresh() {
        _isWifiOnline.value = NetworkStateProvider.isWifiAvailable(appContext)
    }
}
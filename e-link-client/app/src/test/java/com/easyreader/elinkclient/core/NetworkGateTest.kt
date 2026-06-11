package com.easyreader.elinkclient.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class NetworkGateTest {
    @Test
    fun canUseNetworkReturnsProviderState() {
        var online = false
        val gate = NetworkGate { online }

        assertFalse(gate.canUseNetwork())

        online = true

        assertTrue(gate.canUseNetwork())
    }

    @Test
    fun requireWifiOnlineAllowsOnlineState() {
        val gate = NetworkGate { true }

        gate.requireWifiOnline("test")
    }

    @Test
    fun requireWifiOnlineThrowsWhenOffline() {
        val gate = NetworkGate { false }

        val error = runCatching {
            gate.requireWifiOnline("sync")
        }.exceptionOrNull()

        assertTrue(error is NetworkDisabledException)
        assertEquals("sync", (error as NetworkDisabledException).operation)
    }
}
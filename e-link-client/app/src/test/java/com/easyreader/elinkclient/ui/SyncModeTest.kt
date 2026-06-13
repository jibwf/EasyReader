package com.easyreader.elinkclient.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class SyncModeTest {

    @Test
    fun fromStorageReturnsAutoOnWifiForNull() {
        assertEquals(SyncMode.AUTO_ON_WIFI, SyncMode.fromStorage(null))
    }

    @Test
    fun fromStorageReturnsAutoOnWifiForEmpty() {
        assertEquals(SyncMode.AUTO_ON_WIFI, SyncMode.fromStorage(""))
    }

    @Test
    fun fromStorageReturnsAutoOnWifiForInvalid() {
        assertEquals(SyncMode.AUTO_ON_WIFI, SyncMode.fromStorage("invalid"))
    }

    @Test
    fun fromStorageReturnsAutoOnWifiForLegacyManualOnly() {
        assertEquals(SyncMode.AUTO_ON_WIFI, SyncMode.fromStorage("manual_only"))
    }

    @Test
    fun fromStorageReturnsAutoOnWifi() {
        assertEquals(SyncMode.AUTO_ON_WIFI, SyncMode.fromStorage("AUTO_ON_WIFI"))
    }

    @Test
    fun storageValueRoundTrips() {
        SyncMode.entries.forEach { mode ->
            assertEquals(mode, SyncMode.fromStorage(mode.storageValue))
        }
    }
}

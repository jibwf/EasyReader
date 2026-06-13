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
    fun fromStorageReturnsManualProgressOnly() {
        assertEquals(SyncMode.MANUAL_PROGRESS_ONLY, SyncMode.fromStorage("manual_only"))
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

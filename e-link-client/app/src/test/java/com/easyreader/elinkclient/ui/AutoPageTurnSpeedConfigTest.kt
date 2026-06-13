package com.easyreader.elinkclient.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class AutoPageTurnSpeedConfigTest {

    @Test
    fun normalizeClampsToMinValue() {
        assertEquals(AutoPageTurnSpeedConfig.MIN_INTERVAL_MS, AutoPageTurnSpeedConfig.normalize(1000L))
    }

    @Test
    fun normalizeClampsToMaxValue() {
        assertEquals(AutoPageTurnSpeedConfig.MAX_INTERVAL_MS, AutoPageTurnSpeedConfig.normalize(100000L))
    }

    @Test
    fun normalizeReturnsSameValueInRange() {
        assertEquals(15000L, AutoPageTurnSpeedConfig.normalize(15000L))
    }

    @Test
    fun fromStorageParsesNumericValue() {
        assertEquals(20000L, AutoPageTurnSpeedConfig.fromStorage("20000"))
    }

    @Test
    fun fromStorageHandlesLegacySlow() {
        assertEquals(10000L, AutoPageTurnSpeedConfig.fromStorage("SLOW"))
    }

    @Test
    fun fromStorageHandlesLegacyMedium() {
        assertEquals(AutoPageTurnSpeedConfig.DEFAULT_INTERVAL_MS, AutoPageTurnSpeedConfig.fromStorage("MEDIUM"))
    }

    @Test
    fun fromStorageHandlesLegacyFast() {
        assertEquals(AutoPageTurnSpeedConfig.MIN_INTERVAL_MS, AutoPageTurnSpeedConfig.fromStorage("FAST"))
    }

    @Test
    fun fromStorageReturnsDefaultForInvalid() {
        assertEquals(AutoPageTurnSpeedConfig.DEFAULT_INTERVAL_MS, AutoPageTurnSpeedConfig.fromStorage("invalid"))
    }

    @Test
    fun fromStorageReturnsDefaultForNull() {
        assertEquals(AutoPageTurnSpeedConfig.DEFAULT_INTERVAL_MS, AutoPageTurnSpeedConfig.fromStorage(null))
    }

    @Test
    fun toStorageReturnsNormalizedString() {
        assertEquals("15600", AutoPageTurnSpeedConfig.toStorage(15600L))
    }

    @Test
    fun formatLabelShowsSeconds() {
        val label = AutoPageTurnSpeedConfig.formatLabel(15000L)
        assert(label.contains("15"))
        assert(label.contains("秒"))
    }
}

package com.easyreader.elinkclient.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class MainScreenTabRestoreTest {
    @Test
    fun `resolveScreenTab returns matching enum for valid name`() {
        assertEquals(ScreenTab.Search, resolveScreenTab("Search"))
    }

    @Test
    fun `resolveScreenTab falls back to home for invalid value`() {
        assertEquals(ScreenTab.Home, resolveScreenTab("stale-or-corrupted"))
    }
}

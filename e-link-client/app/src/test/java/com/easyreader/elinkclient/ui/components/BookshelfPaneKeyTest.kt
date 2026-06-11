package com.easyreader.elinkclient.ui.components

import com.easyreader.elinkclient.data.model.BookItem
import com.easyreader.elinkclient.data.model.LocalShelfBook
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class BookshelfPaneKeyTest {
    @Test
    fun `section keys remain unique for local and server books with the same book key`() {
        val sharedBookKey = "bk-001"
        val local = LocalShelfBook(
            bookKey = sharedBookKey,
            name = "Local Book",
            bookUrl = "https://books/local",
            sourceUrl = "https://source/local",
        )
        val server = BookItem(
            id = 7,
            bookKey = sharedBookKey,
            name = "Server Book",
            author = "Author",
            coverUrl = "",
            intro = "",
            bookUrl = "https://books/server",
            sourceUrl = "https://source/server",
            totalChapters = 10,
        )

        val keys = setOf(
            localShelfItemKey(local),
            serverShelfItemKey(server),
        )

        assertEquals(2, keys.size)
    }

    @Test
    fun `blank identifiers fall back to deterministic section keys`() {
        val local = LocalShelfBook(
            bookKey = "",
            name = "Fallback Local",
            bookUrl = "https://books/local",
            sourceUrl = "https://source/local",
        )
        val server = BookItem(
            id = 9,
            bookKey = "",
            name = "Fallback Server",
            author = "Author",
            coverUrl = "",
            intro = "",
            bookUrl = "https://books/server",
            sourceUrl = "https://source/server",
            totalChapters = 3,
        )

        val localKey = localShelfItemKey(local)
        val serverKey = serverShelfItemKey(server)

        assertNotEquals(localKey, serverKey)
        assertEquals("local:https://books/local|https://source/local|Fallback Local", localKey)
        assertEquals("server:9|https://books/server|https://source/server", serverKey)
    }
}

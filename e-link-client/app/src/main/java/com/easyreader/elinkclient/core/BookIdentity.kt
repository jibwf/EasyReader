package com.easyreader.elinkclient.core

object BookIdentity {
    fun resolveBookKey(rawBookKey: String?, sourceUrl: String, bookUrl: String): String {
        val normalized = rawBookKey?.trim().orEmpty()
        require(normalized.isNotEmpty()) {
            "book_key is required for sourceUrl=$sourceUrl, bookUrl=$bookUrl"
        }
        return normalized
    }
}

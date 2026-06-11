package com.easyreader.elinkclient.core

class NetworkDisabledException(
    val operation: String,
) : IllegalStateException("WiFi is unavailable for operation: $operation")
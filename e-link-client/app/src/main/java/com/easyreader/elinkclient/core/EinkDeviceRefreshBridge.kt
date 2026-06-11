package com.easyreader.elinkclient.core

import android.view.View
import java.lang.reflect.Modifier

object EinkDeviceRefreshBridge {
    fun apply(targetView: View, action: RefreshAction) {
        if (action == RefreshAction.NONE) {
            return
        }

        val handled = tryVendorStaticApi(targetView, action) || tryVendorViewApi(targetView, action)
        if (!handled) {
            targetView.postInvalidateOnAnimation()
            targetView.invalidate()
        }
    }

    private fun tryVendorStaticApi(targetView: View, action: RefreshAction): Boolean {
        val modeValue = if (action == RefreshAction.FULL) 2 else 1
        val candidates = listOf(
            "com.onyx.android.sdk.api.device.epd.EpdController",
            "com.onyx.android.sdk.api.device.epd.EpdControllerCompat",
            "com.onyx.android.sdk.api.device.EpdController",
        )
        val methodNames = listOf(
            "invalidate",
            "refreshScreen",
            "setViewDefaultUpdateMode",
            "setViewUpdateMode",
        )

        for (className in candidates) {
            val clazz = runCatching { Class.forName(className) }.getOrNull() ?: continue
            for (methodName in methodNames) {
                val method = clazz.methods.firstOrNull {
                    it.name == methodName && Modifier.isStatic(it.modifiers)
                } ?: continue

                val invoked = runCatching {
                    when (method.parameterCount) {
                        1 -> {
                            val p0 = method.parameterTypes[0]
                            when {
                                p0.isAssignableFrom(View::class.java) -> method.invoke(null, targetView)
                                p0 == Int::class.javaPrimitiveType || p0 == Int::class.java -> method.invoke(null, modeValue)
                                else -> return@runCatching false
                            }
                        }

                        2 -> {
                            val p0 = method.parameterTypes[0]
                            val p1 = method.parameterTypes[1]
                            if (
                                p0.isAssignableFrom(View::class.java) &&
                                (p1 == Int::class.javaPrimitiveType || p1 == Int::class.java)
                            ) {
                                method.invoke(null, targetView, modeValue)
                            } else {
                                return@runCatching false
                            }
                        }

                        else -> return@runCatching false
                    }
                    true
                }.getOrDefault(false)

                if (invoked) {
                    targetView.postInvalidateOnAnimation()
                    return true
                }
            }
        }
        return false
    }

    private fun tryVendorViewApi(targetView: View, action: RefreshAction): Boolean {
        val modeValue = if (action == RefreshAction.FULL) 2 else 1
        val methodNames = listOf("setEpdMode", "setUpdateMode", "setRefreshMode")

        for (methodName in methodNames) {
            val method = targetView.javaClass.methods.firstOrNull {
                it.name == methodName && it.parameterCount == 1 &&
                    (it.parameterTypes[0] == Int::class.javaPrimitiveType || it.parameterTypes[0] == Int::class.java)
            } ?: continue

            val invoked = runCatching {
                method.invoke(targetView, modeValue)
                true
            }.getOrDefault(false)

            if (invoked) {
                targetView.postInvalidateOnAnimation()
                return true
            }
        }

        return false
    }
}

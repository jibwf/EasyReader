package com.easyreader.elinkclient.data.network

import android.content.Context
import com.easyreader.elinkclient.core.DeviceProfile
import com.easyreader.elinkclient.core.NetworkGate
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.Cache
import okhttp3.ConnectionPool
import okhttp3.Dispatcher
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import java.io.File
import java.util.concurrent.TimeUnit

object NetworkModule {
    fun createHttpClient(context: Context, networkGate: NetworkGate): OkHttpClient {
        val isLowRamDevice = DeviceProfile.isLowRamDevice(context)
        val cacheSizeBytes = if (isLowRamDevice) {
            4L * 1024L * 1024L
        } else {
            10L * 1024L * 1024L
        }
        val dispatcher = Dispatcher().apply {
            maxRequests = if (isLowRamDevice) 4 else 8
            maxRequestsPerHost = if (isLowRamDevice) 2 else 4
        }

        return OkHttpClient.Builder()
            .addInterceptor { chain ->
                val request = chain.request()
                networkGate.requireWifiOnline("${request.method} ${request.url.encodedPath}")
                chain.proceed(request)
            }
            .dispatcher(dispatcher)
            .connectionPool(
                ConnectionPool(
                    if (isLowRamDevice) 2 else 4,
                    5,
                    TimeUnit.MINUTES,
                )
            )
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .cache(Cache(File(context.cacheDir, "http-client"), cacheSizeBytes))
            .build()
    }

    fun createMoshi(): Moshi {
        return Moshi.Builder()
            .add(KotlinJsonAdapterFactory())
            .build()
    }

    fun createApi(
        baseUrl: String,
        client: OkHttpClient,
        moshi: Moshi = createMoshi(),
    ): EasyReaderApi {
        val retrofit = Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(client)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()

        return retrofit.create(EasyReaderApi::class.java)
    }
}

# Android Kotlin Starter (Retrofit + JWT + Outbox-ready DTO)

Ниже базовый стартовый набор для Android-проекта (Kotlin), совместимый с текущим `UtilBase /api/v1`.

## 1) DTO модели

```kotlin
package com.example.utilbase.api.dto

data class ApiErrorEnvelope(
    val error: ApiError
)

data class ApiError(
    val code: String,
    val message: String
)

data class LoginRequest(
    val username: String,
    val password: String
)

data class TokenResponse(
    val access_token: String,
    val refresh_token: String,
    val token_type: String,
    val expires_in: Int
)

data class LogoutRequest(
    val refresh_token: String
)

data class MeResponse(
    val id: Long,
    val username: String,
    val role: String,
    val worker_id: Long?,
    val resolved_worker_id: Long?
)

data class RequestListResponse(
    val items: List<RequestDto>,
    val total: Int,
    val limit: Int,
    val offset: Int
)

data class RequestDto(
    val id: Long,
    val request_number: String?,
    val description: String?,
    val status: String?,
    val mode: String?,
    val service_type: String?,
    val visit_type: String?,
    val planned_date: String?,
    val full_name: String?,
    val address: String?,
    val phone: String?
)

data class ClientOperationBody(
    val client_operation_id: String
)

data class RequestModeBody(
    val mode: String,
    val client_operation_id: String
)

data class ChecklistSubmitBody(
    val items: List<ChecklistAnswerBody>
)

data class ChecklistAnswerBody(
    val item_id: Long,
    val checked: Boolean? = null,
    val value_text: String? = null,
    val value_number: Double? = null,
    val media_id: Long? = null
)

data class AddItemBody(
    val item_type: String = "material",
    val name: String,
    val quantity: Double = 1.0,
    val unit_price: Double = 0.0,
    val source: String? = null,
    val comment: String? = null,
    val client_operation_id: String
)

data class PatchItemBody(
    val name: String? = null,
    val quantity: Double? = null,
    val unit_price: Double? = null,
    val source: String? = null,
    val comment: String? = null,
    val client_operation_id: String
)

data class AddPaymentBody(
    val amount: Double,
    val payment_method: String = "cash",
    val is_cash: Boolean = true,
    val note: String? = null,
    val client_operation_id: String
)

data class AddChatMessageBody(
    val message_text: String,
    val client_operation_id: String
)
```

## 2) Retrofit API interface

```kotlin
package com.example.utilbase.api

import com.example.utilbase.api.dto.*
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.*

interface UtilBaseApi {

    @POST("auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("auth/refresh")
    suspend fun refreshToken(): TokenResponse

    @POST("auth/logout")
    suspend fun logout(@Body body: LogoutRequest): Response<Unit>

    @GET("auth/me")
    suspend fun me(): MeResponse

    @GET("requests")
    suspend fun listRequests(
        @Query("filter") filter: String? = null,
        @Query("limit") limit: Int? = null,
        @Query("offset") offset: Int? = null
    ): RequestListResponse

    @GET("requests/{id}")
    suspend fun getRequest(@Path("id") id: Long): RequestDto

    @POST("requests/{id}/take")
    suspend fun takeRequest(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: ClientOperationBody
    ): RequestDto

    @POST("requests/{id}/mode")
    suspend fun setMode(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: RequestModeBody
    ): RequestDto

    @POST("requests/{id}/close")
    suspend fun closeRequest(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: ClientOperationBody
    ): RequestDto

    @POST("requests/{id}/checklist-submit")
    suspend fun submitChecklist(
        @Path("id") id: Long,
        @Body body: ChecklistSubmitBody
    ): Response<Unit>

    @POST("requests/{id}/items")
    suspend fun addItem(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: AddItemBody
    ): Response<Unit>

    @PATCH("requests/{id}/items/{itemId}")
    suspend fun patchItem(
        @Path("id") id: Long,
        @Path("itemId") itemId: Long,
        @Body body: PatchItemBody
    ): Response<Unit>

    @DELETE("requests/{id}/items/{itemId}")
    suspend fun deleteItem(
        @Path("id") id: Long,
        @Path("itemId") itemId: Long,
        @Header("X-Client-Operation-Id") opId: String
    ): Response<Unit>

    @POST("requests/{id}/payments")
    suspend fun addPayment(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: AddPaymentBody
    ): Response<Unit>

    @POST("requests/{id}/chat/messages")
    suspend fun addChatMessage(
        @Path("id") id: Long,
        @Header("X-Client-Operation-Id") opId: String,
        @Body body: AddChatMessageBody
    ): Response<Unit>

    @Multipart
    @POST("requests/{id}/media")
    suspend fun uploadMedia(
        @Path("id") id: Long,
        @Part file: MultipartBody.Part,
        @Part("client_operation_id") clientOperationId: RequestBody,
        @Header("X-Client-Operation-Id") opId: String
    ): Response<Unit>
}
```

## 3) Token storage contract

```kotlin
interface TokenManager {
    suspend fun getAccessToken(): String?
    suspend fun getRefreshToken(): String?
    suspend fun saveTokens(access: String, refresh: String)
    suspend fun clearTokens()
}
```

Хранение: `EncryptedSharedPreferences` или `DataStore + encryption`.

## 4) AuthInterceptor + TokenAuthenticator

```kotlin
class AuthInterceptor(
    private val tokenManager: TokenManager
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): okhttp3.Response {
        val token = kotlinx.coroutines.runBlocking { tokenManager.getAccessToken() }
        val req = if (token.isNullOrBlank()) {
            chain.request()
        } else {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        }
        return chain.proceed(req)
    }
}
```

```kotlin
class TokenAuthenticator(
    private val tokenManager: TokenManager,
    private val authApi: UtilBaseApi
) : okhttp3.Authenticator {
    override fun authenticate(route: okhttp3.Route?, response: okhttp3.Response): okhttp3.Request? {
        if (responseCount(response) >= 2) return null
        val newTokens = runCatching {
            kotlinx.coroutines.runBlocking { authApi.refreshToken() }
        }.getOrNull() ?: return null

        kotlinx.coroutines.runBlocking {
            tokenManager.saveTokens(newTokens.access_token, newTokens.refresh_token)
        }
        return response.request.newBuilder()
            .header("Authorization", "Bearer ${newTokens.access_token}")
            .build()
    }

    private fun responseCount(response: okhttp3.Response): Int {
        var r: okhttp3.Response? = response
        var count = 1
        while (r?.priorResponse != null) {
            count++
            r = r.priorResponse
        }
        return count
    }
}
```

Важно: `refreshToken()` должен ходить отдельным `OkHttpClient` без этого же `Authenticator`, чтобы не зациклиться.

## 5) Retrofit/OkHttp build

```kotlin
val okHttp = OkHttpClient.Builder()
    .addInterceptor(AuthInterceptor(tokenManager))
    .authenticator(TokenAuthenticator(tokenManager, authApiNoAuth))
    .build()

val retrofit = Retrofit.Builder()
    .baseUrl("https://your-host/api/v1/")
    .client(okHttp)
    .addConverterFactory(MoshiConverterFactory.create())
    .build()
```

## 6) Outbox integration hint

- Для каждого mutation генерируйте `UUID`.
- Сохраняйте как `client_operation_id` в локальную очередь.
- На отправке используйте и body, и header `X-Client-Operation-Id`.
- При `409 conflict_fsm` не ретраить автоматически.

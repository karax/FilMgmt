// Relative API paths keep the browser on the Vite origin. During development,
// Vite proxies /api to the local FastAPI server, including for Tailnet clients.
const DEFAULT_API_BASE_URL = ''

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL?.trim() || DEFAULT_API_BASE_URL
).replace(/\/$/, '')

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(message: string, status: number, detail: unknown = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/**
 * Uses an API-error shape rather than only `instanceof`. Vite HMR can retain
 * an error created by an earlier module instance, for which `instanceof`
 * would incorrectly return false.
 */
export function isApiError(error: unknown): error is ApiError {
  return typeof error === 'object'
    && error !== null
    && 'status' in error
    && typeof (error as { status?: unknown }).status === 'number'
    && 'detail' in error
}

async function request<T>(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
    ...init,
  })

  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new ApiError(
      `API request failed with status ${response.status}.`,
      response.status,
      detail,
    )
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: 'GET' }, signal)
}

export function apiPost<TResponse, TPayload>(
  path: string,
  payload: TPayload,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function apiPostWithoutBody<TResponse>(path: string): Promise<TResponse> {
  return request<TResponse>(path, { method: 'POST' })
}

export function apiPostFormData<TResponse>(
  path: string,
  formData: FormData,
): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'POST',
    body: formData,
  })
}

export function apiPatch<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'PATCH',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function apiPut<TResponse, TPayload>(path: string, payload: TPayload): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'PUT',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function apiDelete(path: string): Promise<void> {
  return request<void>(path, { method: 'DELETE' })
}

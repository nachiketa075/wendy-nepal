// Thin wrapper around fetch for the FastAPI backend (same origin, under /api).

export class ApiError extends Error {
  constructor(status, code, message, fields = {}) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

let csrfToken = null
export const setCsrfToken = (token) => {
  csrfToken = token
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (csrfToken && method !== 'GET') headers['X-CSRF-Token'] = csrfToken

  let response
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError(0, 'network_error', 'We could not reach the server. Please check your connection and try again.')
  }

  if (response.status === 204) return null
  let data = null
  try {
    data = await response.json()
  } catch {
    // Non-JSON body (for example a proxy error page); handled below.
  }
  if (!response.ok || data === null) {
    const error = data?.error
    throw new ApiError(
      response.status,
      error?.code || 'server_error',
      error?.message || 'Something went wrong on our side. Please try again.',
      error?.fields || {},
    )
  }
  return data
}

import { errorMessage } from '../i18n'

const jsonHeaders = { 'Content-Type': 'application/json' }

export async function api(path, options = {}) {
  let response
  try {
    response = await fetch(path, { credentials: 'same-origin', ...options })
  } catch (cause) {
    const exception = new Error(errorMessage({ code: 'network_error', message: cause.message }))
    exception.code = 'network_error'
    throw exception
  }
  const type = response.headers.get('content-type') || ''
  const body = type.includes('application/json') ? await response.json() : await response.text()
  if (!response.ok) {
    const error = body?.error || { code: 'request_failed', message: 'Request failed' }
    const exception = new Error(errorMessage(error))
    exception.code = error.code
    exception.status = response.status
    exception.details = error.details
    throw exception
  }
  return body
}

export function get(path) { return api(path) }
export function post(path, body) { return api(path, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(body) }) }
export function patch(path, body) { return api(path, { method: 'PATCH', headers: jsonHeaders, body: JSON.stringify(body) }) }
export function remove(path) { return api(path, { method: 'DELETE' }) }

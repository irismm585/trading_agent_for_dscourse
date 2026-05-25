export interface RetryOptions {
  maxRetries?: number
  initialDelay?: number
  maxDelay?: number
  timeout?: number
  shouldRetry?: (error: Error, attempt: number) => boolean
}

const DEFAULT_OPTIONS: Required<RetryOptions> = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  timeout: 30000,
  shouldRetry: (error: Error, attempt: number) => {
    const retryableErrors = [
      'AbortError',
      'NetworkError',
      'TypeError',
      'Failed to fetch',
      'Network request failed',
    ]
    return retryableErrors.some(err => error.name.includes(err) || error.message.includes(err))
  },
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function calculateDelay(attempt: number, initialDelay: number, maxDelay: number): number {
  const exponentialDelay = initialDelay * Math.pow(2, attempt)
  const jitter = Math.random() * 0.3 * exponentialDelay
  return Math.min(exponentialDelay + jitter, maxDelay)
}

export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retryOptions: RetryOptions = {},
): Promise<Response> {
  const { maxRetries, initialDelay, maxDelay, timeout, shouldRetry } = {
    ...DEFAULT_OPTIONS,
    ...retryOptions,
  }

  let lastError: Error | null = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), timeout)

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      })
      clearTimeout(timeoutId)

      if (response.ok) {
        return response
      }

      const errorText = await response.text().catch(() => '')
      lastError = new Error(`HTTP ${response.status}: ${response.statusText}${errorText ? ` - ${errorText}` : ''}`)
      lastError.name = 'HTTPError'

      if (response.status >= 500 && attempt < maxRetries) {
        const delayMs = calculateDelay(attempt, initialDelay, maxDelay)
        console.warn(`[fetchWithRetry] HTTP ${response.status}, 重试 ${attempt + 1}/${maxRetries}，等待 ${delayMs}ms...`)
        await delay(delayMs)
        continue
      }

      throw lastError
    } catch (error) {
      clearTimeout(timeoutId)

      const err = error instanceof Error ? error : new Error(String(error))
      lastError = err

      if (attempt < maxRetries && shouldRetry(err, attempt)) {
        const delayMs = calculateDelay(attempt, initialDelay, maxDelay)
        console.warn(`[fetchWithRetry] 请求失败: ${err.message}，重试 ${attempt + 1}/${maxRetries}，等待 ${delayMs}ms...`)
        await delay(delayMs)
        continue
      }

      throw err
    }
  }

  throw lastError || new Error('请求失败')
}

export async function fetchJsonWithRetry<T = any>(
  url: string,
  options: RequestInit = {},
  retryOptions: RetryOptions = {},
): Promise<T> {
  const response = await fetchWithRetry(url, options, retryOptions)
  return response.json()
}

export async function fetchTextWithRetry(
  url: string,
  options: RequestInit = {},
  retryOptions: RetryOptions = {},
): Promise<string> {
  const response = await fetchWithRetry(url, options, retryOptions)
  return response.text()
}

export const API_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  timeout: 60000,
}

export const HEALTH_CHECK_OPTIONS: RetryOptions = {
  maxRetries: 2,
  initialDelay: 500,
  maxDelay: 2000,
  timeout: 5000,
}

export const SESSION_CREATE_OPTIONS: RetryOptions = {
  maxRetries: 3,
  initialDelay: 2000,
  maxDelay: 15000,
  timeout: 120000,
}

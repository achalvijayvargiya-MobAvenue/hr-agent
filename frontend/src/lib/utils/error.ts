export function getErrorMessage(error: unknown): string | null {
  if (!error) return null

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const axiosError = error as any

  // Try to get message from our standard backend error format
  const backendMessage = axiosError.response?.data?.message
  if (backendMessage) {
    return backendMessage
  }

  // Fallback to detail array if it's a Pydantic validation error that slipped through
  const backendDetail = axiosError.response?.data?.detail
  if (Array.isArray(backendDetail)) {
    return backendDetail[0]?.msg || 'Validation error'
  } else if (typeof backendDetail === 'string') {
    return backendDetail
  }

  // Fallback to Axios or standard JS Error message
  if (axiosError.message) {
    // Hide standard axios generic errors if possible, but keep for debugging if no response
    if (axiosError.message.includes('status code')) {
      return 'The server encountered an issue processing your request.'
    }
    return axiosError.message
  }

  return String(error)
}

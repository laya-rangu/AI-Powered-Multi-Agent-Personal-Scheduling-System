const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers ?? {}),
    },
    ...options,
  })

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text()

  if (!response.ok) {
    const detail =
      typeof payload === 'object' && payload && 'detail' in payload
        ? payload.detail
        : 'Request failed'
    const error = new Error(detail)
    error.status = response.status
    throw error
  }

  return payload
}

export function getApiBaseUrl() {
  return API_BASE_URL
}

export function getDashboardToday() {
  return request('/dashboard/today')
}

export function getNotifications() {
  return request('/notifications')
}

export function updateNotification(id, status) {
  return request(`/notifications/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
}

export function getTasks() {
  return request('/tasks')
}

export function createTask(task) {
  return request('/tasks', {
    method: 'POST',
    body: JSON.stringify(task),
  })
}

export function updateTask(id, updates) {
  return request(`/tasks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  })
}

export function getGoals() {
  return request('/goals')
}

export function getGoalProgress() {
  return request('/goals/progress')
}

export function createGoal(goal) {
  return request('/goals', {
    method: 'POST',
    body: JSON.stringify(goal),
  })
}

export function getDailyPlan(targetDate) {
  return request(`/daily/plan?date=${targetDate}`)
}

export function generateDailyPlan(targetDate) {
  return request('/daily/plan', {
    method: 'POST',
    body: JSON.stringify({ date: targetDate }),
  })
}

export function getAgentLogs(targetDate) {
  return request(`/agent-logs?date=${targetDate}`)
}

export function createCalendarEvent(event) {
  return request('/calendar/events', {
    method: 'POST',
    body: JSON.stringify(event),
  })
}

export function getCalendarEvents(targetDate) {
  return request(`/calendar/events?date=${targetDate}`)
}

export function runAssistantPlan(date, message, model) {
  return request('/assistant/daily-plan', {
    method: 'POST',
    body: JSON.stringify({
      date,
      message,
      ...(model ? { model } : {}),
    }),
  })
}

const _apiBaseRaw = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'; const API_BASE = _apiBaseRaw.includes('/api/v1') ? _apiBaseRaw.replace(/\/+$/g, '') : _apiBaseRaw.replace(/\/+$/g, '') + '/api/v1'

function getToken() {
  return localStorage.getItem('token')
}

function errorMessage(err) {
  if (typeof err.detail === 'string') return err.detail
  if (Array.isArray(err.detail)) return err.detail.map((d) => d.msg || d.loc?.join('.')).join(', ')
  return JSON.stringify(err.detail ?? err)
}

function handleUnauthorized(res) {
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
}

export async function api(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = { ...options.headers }
  if (!headers['Content-Type'] && options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(url, { ...options, headers })
  handleUnauthorized(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err))
  }
  if (res.status === 204) return null
  return res.json()
}

export async function apiUpload(path, fileOrForm) {
  const body = fileOrForm instanceof FormData ? fileOrForm : (() => {
    const form = new FormData()
    form.append('file', fileOrForm)
    return form
  })()
  return api(path, { method: 'POST', body })
}

function triggerDownload(blob, filename) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

export async function apiDownload(path, options = {}, defaultFilename = 'download') {
  if (path.startsWith('data:')) {
    const base64 = path.split(',')[1]
    if (!base64) throw new Error('Data URL invalida')
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
    const blob = new Blob([bytes])
    triggerDownload(blob, defaultFilename)
    return
  }

  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = { ...options.headers }
  if (!headers['Content-Type'] && options.body !== undefined && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(url, { ...options, headers })
  handleUnauthorized(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(errorMessage(err))
  }
  const blob = await res.blob()

  let filename = defaultFilename
  const disposition = res.headers.get('Content-Disposition')
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename="?([^"]+)"?/)
    if (match && match[1]) filename = match[1]
  }

  triggerDownload(blob, filename)
}

// --- Auth ---
export async function login(email, password) {
  return api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function register(email, password, full_name) {
  return api('/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, full_name }),
  })
}

export async function fetchMe() {
  return api('/auth/me')
}

export async function refreshToken() {
  return api('/auth/refresh', { method: 'POST' })
}

// --- Projects ---
export async function listProjects() {
  return api('/projects')
}

export async function createProject(body) {
  return api('/projects', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function getProject(projectId) {
  return api(`/projects/${projectId}`)
}

export async function deleteProject(projectId) {
  return api(`/projects/${projectId}`, { method: 'DELETE' })
}

// --- Users ---
export async function listUsers() {
  return api('/users')
}

export async function createUser(body) {
  return api('/users', { method: 'POST', body: JSON.stringify(body) })
}

export async function updateUser(id, body) {
  return api(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

// --- School Data ---
export function uploadSchoolData(projectId, file, schoolCode) {
  const form = new FormData()
  form.append('file', file)
  form.append('school_code', schoolCode)
  return apiUpload(`/projects/${projectId}/school-data/upload`, form)
}

export function getSchoolDataSummary(projectId) {
  return api(`/projects/${projectId}/school-data/summary`)
}

export function listTeachers(projectId) {
  return api(`/projects/${projectId}/teachers`)
}

export function listSubjects(projectId) {
  return api(`/projects/${projectId}/subjects`)
}

export function listSections(projectId, shift, grade) {
  let params = []
  if (shift) params.push(`shift=${shift}`)
  if (grade) params.push(`grade=${grade}`)
  const qs = params.length ? `?${params.join('&')}` : ''
  return api(`/projects/${projectId}/sections${qs}`)
}

export function listTimeSlots(projectId, shift) {
  const qs = shift ? `?shift=${shift}` : ''
  return api(`/projects/${projectId}/time-slots${qs}`)
}

export function listGradeLoads(projectId) {
  return api(`/projects/${projectId}/grade-loads`)
}

export function deleteSchoolData(projectId) {
  return api(`/projects/${projectId}/school-data`, { method: 'DELETE' })
}

// --- Schedule ---
export function generateSchedule(projectId, shift, label) {
  return api(`/projects/${projectId}/schedules/generate`, {
    method: 'POST',
    body: JSON.stringify({ shift, label }),
  })
}

export function listScheduleVersions(projectId) {
  return api(`/projects/${projectId}/schedules`)
}

export function getScheduleVersion(projectId, versionId) {
  return api(`/projects/${projectId}/schedules/${versionId}`)
}

export function getScheduleEntries(projectId, versionId, sectionId) {
  const qs = sectionId ? `?section_id=${sectionId}` : ''
  return api(`/projects/${projectId}/schedules/${versionId}/entries${qs}`)
}

export function validateSchedule(projectId, versionId) {
  return api(`/projects/${projectId}/schedules/${versionId}/validate`, { method: 'POST' })
}

export function validateAndApprove(projectId, versionId) {
  return api(`/projects/${projectId}/schedules/${versionId}/validate-and-approve`, { method: 'POST' })
}

// --- Export ---
export function exportScheduleExcel(projectId, versionId) {
  return apiDownload(`/projects/${projectId}/schedules/${versionId}/export`, {}, `horario_v${versionId}.xlsx`)
}

// --- Schedule Swap / Move ---
export function swapScheduleEntries(projectId, versionId, entryIdA, entryIdB) {
  return api(`/projects/${projectId}/schedules/${versionId}/swap`, {
    method: 'POST',
    body: JSON.stringify({ entry_id_a: entryIdA, entry_id_b: entryIdB }),
  })
}

export function moveScheduleEntry(projectId, versionId, entryId, targetTimeSlotId) {
  return api(`/projects/${projectId}/schedules/${versionId}/move`, {
    method: 'POST',
    body: JSON.stringify({ entry_id: entryId, target_time_slot_id: targetTimeSlotId }),
  })
}

// --- Assistant ---
export function sendAssistantMessage(projectId, content, scheduleVersionId) {
  return api(`/projects/${projectId}/assistant/chat`, {
    method: 'POST',
    body: JSON.stringify({ content, schedule_version_id: scheduleVersionId }),
  })
}

export function applyAssistantActions(projectId, messageId) {
  return api(`/projects/${projectId}/assistant/apply`, {
    method: 'POST',
    body: JSON.stringify({ message_id: messageId }),
  })
}

export function getAssistantHistory(projectId, scheduleVersionId) {
  return api(`/projects/${projectId}/assistant/history?schedule_version_id=${scheduleVersionId}`)
}

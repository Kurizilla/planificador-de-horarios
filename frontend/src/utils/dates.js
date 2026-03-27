const APP_TIMEZONE = 'America/El_Salvador' // UTC-6, no DST

/**
 * Formats an ISO 8601 datetime string for display in El Salvador local time.
 * Example output: "Mar 10, 2025, 2:30 PM"
 */
export function formatDateTime(isoString) {
  if (!isoString) return '—'
  return new Intl.DateTimeFormat('en-US', {
    timeZone: APP_TIMEZONE,
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(isoString))
}

/**
 * Returns today's date as YYYY-MM-DD in El Salvador local time.
 * Used for download filenames so the date reflects local time, not UTC.
 */
export function todayLocalDate() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: APP_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const y = parts.find((p) => p.type === 'year').value
  const m = parts.find((p) => p.type === 'month').value
  const d = parts.find((p) => p.type === 'day').value
  return `${y}-${m}-${d}`
}

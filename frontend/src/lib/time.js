export const BUSINESS_TZ = 'Asia/Kathmandu'
export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

const pad = (n) => String(n).padStart(2, '0')

/** Current date ("YYYY-MM-DD") and minutes since midnight in Pokhara. */
export function nowInBusinessTz() {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-CA', {
      timeZone: BUSINESS_TZ,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date())
      .map((p) => [p.type, p.value]),
  )
  return { date: `${parts.year}-${parts.month}-${parts.day}`, minutes: Number(parts.hour) * 60 + Number(parts.minute) }
}

export function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + days)
  return d.toISOString().slice(0, 10)
}

/** 0 = Monday … 6 = Sunday, matching the backend. */
export function weekdayOf(isoDate) {
  return (new Date(`${isoDate}T00:00:00Z`).getUTCDay() + 6) % 7
}

export const toMinutes = (hhmm) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5))
export const fromMinutes = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`

export function formatTime(hhmm) {
  const m = toMinutes(hhmm)
  const h = Math.floor(m / 60)
  return `${h % 12 || 12}:${pad(m % 60)} ${h < 12 ? 'AM' : 'PM'}`
}

export function formatDate(isoDate) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC',
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(new Date(`${isoDate}T00:00:00Z`))
}

export function formatDateTime(isoString) {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: BUSINESS_TZ,
    day: 'numeric',
    month: 'short',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(isoString))
}

/** Requestable times for a date, from the owner's booking windows. */
export function slotsFor(config, isoDate) {
  if (!config || !isoDate) return []
  const now = nowInBusinessTz()
  const earliest = isoDate === now.date ? now.minutes + config.min_lead_minutes : -1
  const slots = []
  for (const w of config.windows.filter((w) => w.weekday === weekdayOf(isoDate))) {
    for (let m = toMinutes(w.start_time); m <= toMinutes(w.end_time); m += config.slot_interval_minutes) {
      if (m >= earliest) slots.push(fromMinutes(m))
    }
  }
  return slots.sort()
}

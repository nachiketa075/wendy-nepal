import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { WEEKDAYS } from '../lib/time.js'

const hhmm = (t) => t.slice(0, 5)

export default function SettingsPanel({ onAuthError }) {
  const [settings, setSettings] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api('/owner/settings')
      .then((data) => setSettings({ ...data, windows: data.windows.map((w) => ({ ...w, start_time: hhmm(w.start_time), end_time: hhmm(w.end_time) })) }))
      .catch((err) => !onAuthError(err) && setMessage({ kind: 'error', text: err.message }))
  }, [onAuthError])

  if (!settings) {
    return <p role={message ? 'alert' : 'status'}>{message?.text || 'Loading settings…'}</p>
  }

  const set = (name, value) => setSettings((s) => ({ ...s, [name]: value }))
  const setWindow = (index, name, value) =>
    setSettings((s) => ({ ...s, windows: s.windows.map((w, i) => (i === index ? { ...w, [name]: value } : w)) }))
  const addWindow = (weekday) => setSettings((s) => ({ ...s, windows: [...s.windows, { weekday, start_time: '08:00', end_time: '18:00' }] }))
  const removeWindow = (index) => setSettings((s) => ({ ...s, windows: s.windows.filter((_, i) => i !== index) }))
  const copyMonday = () =>
    setSettings((s) => {
      const monday = s.windows.filter((w) => w.weekday === 0)
      return { ...s, windows: WEEKDAYS.flatMap((_, day) => monday.map((w) => ({ ...w, weekday: day }))) }
    })

  const save = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setMessage(null)
    try {
      const numbers = Object.fromEntries(
        ['min_party_size', 'max_party_size', 'min_lead_minutes', 'max_advance_days', 'slot_interval_minutes'].map((k) => [k, Number(settings[k])]),
      )
      const saved = await api('/owner/settings', { method: 'PUT', body: { ...settings, ...numbers } })
      setSettings({ ...saved, windows: saved.windows.map((w) => ({ ...w, start_time: hhmm(w.start_time), end_time: hhmm(w.end_time) })) })
      setMessage({ kind: 'ok', text: 'Settings saved. New requests follow these rules straight away.' })
    } catch (err) {
      if (!onAuthError(err)) {
        const detail = Object.values(err.fields || {})[0]
        setMessage({ kind: 'error', text: detail ? `Not saved. ${detail}` : `Not saved. ${err.message}` })
      }
    } finally {
      setBusy(false)
    }
  }

  const number = (name, label, hint, props = {}) => (
    <label className="block">
      <span className="field-label">{label}</span>
      <input type="number" className="field" required value={settings[name]} onChange={(e) => set(name, e.target.value)} {...props} />
      {hint && <span className="mt-1 block text-xs opacity-70">{hint}</span>}
    </label>
  )

  return (
    <form onSubmit={save} aria-labelledby="settings-title" className="max-w-4xl">
      <h1 id="settings-title" className="mb-2 text-[40px]">
        Booking settings
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        These rules decide which dates, times and group sizes guests can <em>request</em>. They are not opening hours and
        are not shown as such. All times are Pokhara time.
      </p>

      {!settings.owner_confirmed && (
        <div role="note" className="mb-8 rounded-[20px] border border-amber bg-citrus/40 p-5 text-sm leading-[1.7]">
          <strong>These are provisional demo values.</strong> They were not taken from the shop’s real hours. Review each
          one, tick the confirmation box at the bottom and save. On the live site, online requests stay closed until you
          have done this.
        </div>
      )}

      <div className="mb-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {number('min_party_size', 'Smallest group', null, { min: 1, max: 100 })}
        {number('max_party_size', 'Largest group', 'Bigger groups are asked to call.', { min: 1, max: 100 })}
        {number('min_lead_minutes', 'Minimum notice (minutes)', 'How far ahead a request must be.', { min: 0, max: 10080 })}
        {number('max_advance_days', 'How many days ahead', null, { min: 1, max: 365 })}
        <label className="block">
          <span className="field-label">Time steps</span>
          <select className="field" value={settings.slot_interval_minutes} onChange={(e) => set('slot_interval_minutes', e.target.value)}>
            <option value={15}>Every 15 minutes</option>
            <option value={30}>Every 30 minutes</option>
            <option value={60}>Every hour</option>
          </select>
        </label>
      </div>

      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-[28px] tracking-[-0.6px]">Booking windows</h2>
        <button type="button" className="textlink" onClick={copyMonday}>
          Copy Monday to every day
        </button>
      </div>
      <p className="mb-4 text-sm opacity-80">First and last time a guest may ask for, each day. A day with no window takes no requests.</p>
      <div className="mb-8 divide-y divide-line border-y border-line">
        {WEEKDAYS.map((day, weekday) => {
          const rows = settings.windows.map((w, index) => ({ ...w, index })).filter((w) => w.weekday === weekday)
          return (
            <fieldset key={day} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-3">
              <legend className="float-left w-28 font-semibold">{day}</legend>
              <div className="flex flex-1 flex-col gap-2">
                {rows.length === 0 && <span className="text-sm opacity-65">No requests taken</span>}
                {rows.map((w) => (
                  <div key={w.index} className="flex flex-wrap items-center gap-2 text-sm">
                    <input type="time" required aria-label={`${day} from`} className="field !w-auto !py-2" value={w.start_time} onChange={(e) => setWindow(w.index, 'start_time', e.target.value)} />
                    <span>to</span>
                    <input type="time" required aria-label={`${day} until`} className="field !w-auto !py-2" value={w.end_time} onChange={(e) => setWindow(w.index, 'end_time', e.target.value)} />
                    <button type="button" className="textlink" onClick={() => removeWindow(w.index)} aria-label={`Remove ${day} window ${w.start_time} to ${w.end_time}`}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>
              <button type="button" className="textlink" onClick={() => addWindow(weekday)} aria-label={`Add a window on ${day}`}>
                Add window
              </button>
            </fieldset>
          )
        })}
      </div>

      <label className="mb-3 flex items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 h-5 w-5 accent-forest" checked={settings.booking_enabled} onChange={(e) => set('booking_enabled', e.target.checked)} />
        <span>
          <strong>Accept online table requests.</strong> Untick to pause the form; guests are asked to call instead.
        </span>
      </label>
      <label className="mb-6 flex items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 h-5 w-5 accent-forest" checked={settings.owner_confirmed} onChange={(e) => set('owner_confirmed', e.target.checked)} />
        <span>
          <strong>I have reviewed these settings and they are right for Wendy.</strong> Required before the live site
          accepts requests.
        </span>
      </label>

      <button type="submit" className="pill pill-dark" disabled={busy}>
        {busy ? 'Saving…' : 'Save settings'}
      </button>
      <p role={message?.kind === 'error' ? 'alert' : 'status'} className={`mt-4 min-h-5 text-sm font-medium ${message?.kind === 'error' ? 'text-berry' : ''}`}>
        {message?.text}
      </p>
    </form>
  )
}

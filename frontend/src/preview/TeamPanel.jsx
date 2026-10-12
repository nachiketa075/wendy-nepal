import { useState } from 'react'
import { PREVIEW_EMPLOYEES } from './fixtures.js'
import { PERMISSIONS } from './permissions.js'
import { PreviewTag } from './PreviewBanner.jsx'

/**
 * Owner-side design preview for managing employees and their permissions.
 * Everything here is fictional and held in memory: no employee is created,
 * no permission is stored, and nothing is enforced.
 */
export default function TeamPanel() {
  const [employees, setEmployees] = useState(PREVIEW_EMPLOYEES)
  const [draft, setDraft] = useState({ name: '', email: '' })
  const [notice, setNotice] = useState('')

  const update = (id, change, text) => {
    setEmployees((list) => list.map((e) => (e.id === id ? { ...e, ...change(e) } : e)))
    setNotice(`${text} Preview only: nothing was saved.`)
  }
  const toggle = (id, key) =>
    update(id, (e) => ({ permissions: e.permissions.includes(key) ? e.permissions.filter((k) => k !== key) : [...e.permissions, key] }), 'Permission changed.')

  const add = (event) => {
    event.preventDefault()
    if (!draft.name.trim() || !draft.email.trim()) return
    setEmployees((list) => [...list, { id: `new-${list.length + 1}`, name: draft.name.trim(), email: draft.email.trim(), active: true, permissions: ['view_bookings'] }])
    setDraft({ name: '', email: '' })
    setNotice('Employee added to this preview. Preview only: no account was created and no invitation was sent.')
  }

  return (
    <section aria-labelledby="team-title">
      <h1 id="team-title" className="mb-2 text-[40px]">
        Team &amp; permissions <PreviewTag />
      </h1>
      <div role="note" className="mb-8 max-w-3xl rounded-[5px] border border-amber bg-citrus/40 p-5 text-sm leading-[1.7]">
        <strong>This screen is a design preview with fictional employees.</strong> Staff accounts do not exist yet. Nothing
        you change here is saved, no one can sign in with it, and it does not limit what anyone can do. It becomes real once
        the server supports staff accounts and checks these permissions itself.
      </div>

      <p role="status" className="mb-4 min-h-5 text-sm font-medium">
        {notice}
      </p>

      <ul className="grid gap-4 xl:grid-cols-2">
        {employees.map((employee) => (
          <li key={employee.id} className={`rounded-[5px] border border-line bg-white/60 p-5 ${employee.active ? '' : 'opacity-70'}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-[24px] tracking-[-0.6px]">{employee.name}</h2>
                <p className="break-all text-sm opacity-75">{employee.email}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[1.5px] ${employee.active ? 'bg-forest text-cream' : 'bg-line'}`}>
                {employee.active ? 'Active' : 'Deactivated'}
              </span>
            </div>
            <fieldset disabled={!employee.active} className="mt-4">
              <legend className="field-label">Allowed to</legend>
              <div className="grid gap-2 sm:grid-cols-2">
                {PERMISSIONS.map((p) => (
                  <label key={p.key} className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-1 h-4 w-4 accent-forest" checked={employee.permissions.includes(p.key)} onChange={() => toggle(employee.id, p.key)} />
                    <span>
                      {p.label}
                      <span className="block text-xs opacity-65">{p.hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <button
              type="button"
              className="textlink mt-4"
              onClick={() => update(employee.id, (e) => ({ active: !e.active }), employee.active ? 'Employee deactivated.' : 'Employee reactivated.')}
            >
              {employee.active ? 'Deactivate' : 'Reactivate'}
            </button>
          </li>
        ))}
      </ul>

      <form onSubmit={add} className="mt-8 grid max-w-3xl gap-3 rounded-[5px] bg-sage p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
        <label>
          <span className="field-label">New employee name</span>
          <input className="field" maxLength={120} value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} />
        </label>
        <label>
          <span className="field-label">Email</span>
          <input className="field" type="email" maxLength={254} value={draft.email} onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))} />
        </label>
        <button type="submit" className="pill">
          Add to preview
        </button>
      </form>
    </section>
  )
}

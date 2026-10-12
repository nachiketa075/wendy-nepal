import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { whatsappLink } from '../lib/business.js'
import { useSession } from '../lib/session.jsx'
import { formatDateTime } from '../lib/time.js'

/** Owner only: create employees, set what each may do, deactivate, sign out. */
export default function TeamPanel() {
  const { handleAuthError } = useSession()
  const [employees, setEmployees] = useState(null)
  const [permissions, setPermissions] = useState([])
  const [error, setError] = useState('')
  const [draft, setDraft] = useState({ full_name: '', email: '' })
  const [draftErrors, setDraftErrors] = useState({})
  const [busy, setBusy] = useState(false)
  const [setup, setSetup] = useState(null) // { name, url, expires } shown once

  const load = useCallback(async () => {
    try {
      const [list, perms] = await Promise.all([api('/owner/employees'), api('/owner/permissions')])
      setEmployees(list)
      setPermissions(perms)
    } catch (err) {
      if (!handleAuthError(err)) setError(err.message)
    }
  }, [handleAuthError])

  useEffect(() => {
    load()
  }, [load])

  const showSetup = (data) => setSetup({ name: data.employee.full_name, url: data.setup_url, expires: data.setup_expires_at })

  const add = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setError('')
    setDraftErrors({})
    try {
      showSetup(await api('/owner/employees', { method: 'POST', body: { full_name: draft.full_name.trim(), email: draft.email.trim() } }))
      setDraft({ full_name: '', email: '' })
      await load()
    } catch (err) {
      if (handleAuthError(err)) return
      if (Object.keys(err.fields || {}).length) setDraftErrors(err.fields)
      else setError(`The employee was not added. ${err.message}`)
    } finally {
      setBusy(false)
    }
  }

  if (!employees) return <p role={error ? 'alert' : 'status'}>{error || 'Loading the team…'}</p>

  return (
    <section aria-labelledby="team-title">
      <h1 id="team-title" className="mb-2 text-[40px]">
        Team &amp; permissions
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        New employees start with no permissions. Changes here apply to their very next action, without them signing in
        again. The server checks every permission; hiding a button is not what protects the data.
      </p>
      {error && (
        <p role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
          {error}
        </p>
      )}

      {setup && <SetupLink setup={setup} onClose={() => setSetup(null)} />}

      {employees.length === 0 && <p className="mb-6 rounded-[20px] bg-sage p-8 text-sm">No employees yet. Add the first one below.</p>}
      <ul className="grid gap-4 xl:grid-cols-2">
        {employees.map((employee) => (
          <EmployeeCard key={employee.id} employee={employee} permissions={permissions} onChanged={load} onSetup={showSetup} />
        ))}
      </ul>

      <form onSubmit={add} noValidate className="mt-8 grid max-w-3xl gap-3 rounded-[20px] bg-sage p-5 sm:grid-cols-[1fr_1fr_auto] sm:items-start">
        <label>
          <span className="field-label">New employee name</span>
          <input className="field" maxLength={120} required value={draft.full_name} aria-invalid={Boolean(draftErrors.full_name)} onChange={(e) => setDraft((d) => ({ ...d, full_name: e.target.value }))} />
          {draftErrors.full_name && <span className="field-error block">{draftErrors.full_name}</span>}
        </label>
        <label>
          <span className="field-label">Email (their sign-in)</span>
          <input className="field" type="email" maxLength={254} required value={draft.email} aria-invalid={Boolean(draftErrors.email)} onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))} />
          {draftErrors.email && <span className="field-error block">{draftErrors.email}</span>}
        </label>
        <button type="submit" className="pill sm:mt-[26px]" disabled={busy || !draft.full_name.trim() || !draft.email.trim()}>
          {busy ? 'Adding…' : 'Add employee'}
        </button>
        <p className="text-xs opacity-75 sm:col-span-3">
          You will get a one-time link for them to choose their own password. No email is sent automatically; you pass the
          link on yourself.
        </p>
      </form>
    </section>
  )
}

function SetupLink({ setup, onClose }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(setup.url)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }
  return (
    <div role="status" className="mb-6 rounded-[20px] border border-amber bg-citrus/50 p-5 text-sm leading-[1.7]">
      <p className="font-semibold">Setup link for {setup.name}</p>
      <p>
        Send this link to them privately. It works once, until {formatDateTime(setup.expires)} (Pokhara time), and is not
        shown again. Anyone with the link can set the password, so do not post it publicly.
      </p>
      <input readOnly aria-label="Setup link" className="field my-3 !py-2 font-mono text-xs" value={setup.url} onFocus={(e) => e.target.select()} />
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className="pill pill-dark !py-2" onClick={copy}>
          {copied ? 'Copied' : 'Copy link'}
        </button>
        <a className="pill !py-2" target="_blank" rel="noopener noreferrer" href={whatsappLink('', `Hello ${setup.name}, here is your link to set a password for the Wendy Juice Shop staff page: ${setup.url}`)}>
          Open WhatsApp to send it
        </a>
        <button type="button" className="textlink" onClick={onClose}>
          Done
        </button>
      </div>
    </div>
  )
}

function EmployeeCard({ employee, permissions, onChanged, onSetup }) {
  const { handleAuthError } = useSession()
  const [selected, setSelected] = useState(employee.permissions)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(null)
  const dirty = [...selected].sort().join() !== [...employee.permissions].sort().join()

  const run = async (request, okText, after) => {
    if (busy) return
    setBusy(true)
    setMessage(null)
    try {
      const data = await request()
      after?.(data)
      setMessage({ ok: true, text: okText })
      await onChanged()
    } catch (err) {
      if (!handleAuthError(err)) setMessage({ ok: false, text: `Not saved. ${Object.values(err.fields || {})[0] || err.message}` })
    } finally {
      setBusy(false)
    }
  }
  const patch = (body, okText) => run(() => api(`/owner/employees/${employee.id}`, { method: 'PATCH', body }), okText)
  const toggle = (key) => setSelected((list) => (list.includes(key) ? list.filter((k) => k !== key) : [...list, key]))

  return (
    <li className={`rounded-[20px] border border-line bg-white/60 p-5 ${employee.is_active ? '' : 'opacity-75'}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[24px] tracking-[-0.6px]">{employee.full_name}</h2>
          <p className="break-all text-sm opacity-75">{employee.email}</p>
          <p className="mt-1 text-xs opacity-65">
            {employee.has_password ? 'Password set' : 'Has not chosen a password yet'} · {employee.active_sessions} active sign-in
            {employee.active_sessions === 1 ? '' : 's'}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[1.5px] ${employee.is_active ? 'bg-forest text-cream' : 'bg-line'}`}>
          {employee.is_active ? 'Active' : 'Deactivated'}
        </span>
      </div>

      <fieldset disabled={!employee.is_active || busy} className="mt-4">
        <legend className="field-label">Allowed to</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {permissions.map((p) => (
            <label key={p.key} className="flex items-start gap-2 text-sm">
              <input type="checkbox" className="mt-1 h-4 w-4 accent-forest" checked={selected.includes(p.key)} onChange={() => toggle(p.key)} />
              <span>{p.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button type="button" className="pill !py-2" disabled={busy || !dirty || !employee.is_active} onClick={() => patch({ permissions: selected }, 'Permissions saved. They apply from the next action.')}>
          Save permissions
        </button>
        {employee.is_active ? (
          <>
            <button type="button" className="textlink" disabled={busy} onClick={() => run(() => api(`/owner/employees/${employee.id}/setup-link`, { method: 'POST' }), 'New setup link created; earlier links no longer work.', onSetup)}>
              New password link
            </button>
            <button type="button" className="textlink" disabled={busy || employee.active_sessions === 0} onClick={() => run(() => api(`/owner/employees/${employee.id}/revoke-sessions`, { method: 'POST' }), 'Signed out everywhere.')}>
              Sign out everywhere
            </button>
            <button
              type="button"
              className="textlink"
              disabled={busy}
              onClick={() => window.confirm(`Deactivate ${employee.full_name}? They are signed out at once and cannot sign in.`) && patch({ is_active: false }, 'Deactivated and signed out.')}
            >
              Deactivate
            </button>
          </>
        ) : (
          <button type="button" className="textlink" disabled={busy} onClick={() => patch({ is_active: true }, 'Reactivated.')}>
            Reactivate
          </button>
        )}
      </div>
      <p role={message && !message.ok ? 'alert' : 'status'} className={`mt-3 min-h-5 text-sm font-medium ${message && !message.ok ? 'text-berry' : ''}`}>
        {message?.text}
      </p>
    </li>
  )
}

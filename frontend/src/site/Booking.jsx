import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../lib/api.js'
import { BUSINESS } from '../lib/business.js'
import { addDays, formatDate, formatTime, slotsFor } from '../lib/time.js'
import { Reveal } from './ui.jsx'

const COUNTRY_CODES = [
  ['+977', 'Nepal'],
  ['+91', 'India'],
  ['+61', 'Australia'],
  ['+880', 'Bangladesh'],
  ['+86', 'China'],
  ['+33', 'France'],
  ['+49', 'Germany'],
  ['+972', 'Israel'],
  ['+39', 'Italy'],
  ['+81', 'Japan'],
  ['+31', 'Netherlands'],
  ['+82', 'South Korea'],
  ['+34', 'Spain'],
  ['+94', 'Sri Lanka'],
  ['+44', 'United Kingdom'],
  ['+1', 'USA / Canada'],
]

const EMPTY = {
  full_name: '',
  country_code: '+977',
  custom_code: '',
  phone_number: '',
  email: '',
  requested_date: '',
  requested_time: '',
  party_size: '2',
  special_requests: '',
}

// Which input to focus for an error reported against a backend field name.
const FIELD_INPUT = { phone: 'phone_number' }

const newKey = () =>
  window.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`

function dialCode(form) {
  return form.country_code === 'other' ? `+${form.custom_code.replace(/\D/g, '')}` : form.country_code
}

function fullPhone(form) {
  let digits = form.phone_number.replace(/\D/g, '')
  // A leading 0 is a domestic trunk prefix almost everywhere (Italy keeps it).
  if (dialCode(form) !== '+39') digits = digits.replace(/^0/, '')
  return `${dialCode(form)}${digits}`
}

function validate(form, config, slots) {
  const errors = {}
  if (form.full_name.trim().length < 2) errors.full_name = 'Please tell us your full name.'

  const digits = form.phone_number.replace(/\D/g, '')
  if (form.country_code === 'other' && !/^\+?\d{1,4}$/.test(form.custom_code.trim())) {
    errors.phone = 'Enter your country code, for example 46.'
  } else if (!digits) {
    errors.phone = 'Please add a phone number so we can reach you.'
  } else if (/[^\d\s().-]/.test(form.phone_number) || digits.length < 6 || digits.length > 14) {
    errors.phone = 'Enter your number without the country code, digits only.'
  }

  if (form.email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(form.email.trim())) {
    errors.email = 'That email address doesn’t look right.'
  }

  if (!form.requested_date) errors.requested_date = 'Choose a date.'
  else if (form.requested_date < config.today) errors.requested_date = 'That date has already passed.'
  else if (form.requested_date > addDays(config.today, config.max_advance_days)) {
    errors.requested_date = `Requests can be made up to ${config.max_advance_days} days ahead.`
  } else if (slots.length === 0) errors.requested_date = 'No request times are left for that day. Please pick another date.'
  else if (!form.requested_time) errors.requested_time = 'Choose a time.'
  else if (!slots.includes(form.requested_time)) errors.requested_time = 'Please choose one of the listed times.'

  const size = Number(form.party_size)
  if (!Number.isInteger(size) || size < config.min_party_size || size > config.max_party_size) {
    errors.party_size = `Online requests are for ${config.min_party_size} to ${config.max_party_size} guests.`
  }
  if (form.special_requests.length > 1000) errors.special_requests = 'Please keep this under 1,000 characters.'
  return errors
}

export default function Booking() {
  const [config, setConfig] = useState(null)
  const [configState, setConfigState] = useState('loading') // loading | ready | error
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [status, setStatus] = useState('idle') // idle | submitting | success | error
  const [failure, setFailure] = useState('')
  const [receipt, setReceipt] = useState(null)

  const formRef = useRef(null)
  const successRef = useRef(null)
  const inFlight = useRef(false)
  // One key per distinct set of answers: a retry of the same request reuses it,
  // so the backend stores the booking once however many times it arrives.
  const idempotencyKey = useRef(newKey())

  const loadConfig = () => {
    setConfigState('loading')
    api('/booking/config')
      .then((data) => {
        setConfig(data)
        setConfigState('ready')
      })
      .catch(() => setConfigState('error'))
  }
  useEffect(loadConfig, [])

  const slots = useMemo(() => slotsFor(config, form.requested_date), [config, form.requested_date])

  const update = (name) => (event) => {
    const value = event.target.value
    idempotencyKey.current = newKey()
    setForm((f) => ({ ...f, [name]: value, ...(name === 'requested_date' ? { requested_time: '' } : {}) }))
    const errorKey = ['country_code', 'custom_code', 'phone_number'].includes(name) ? 'phone' : name
    if (errors[errorKey]) setErrors(({ [errorKey]: _, ...rest }) => rest)
    if (status === 'error') setStatus('idle')
  }

  const showErrors = (found) => {
    setErrors(found)
    const first = Object.keys(found)[0]
    // After the next paint, so the fieldset is enabled again when focus moves.
    if (first) requestAnimationFrame(() => formRef.current?.elements[FIELD_INPUT[first] || first]?.focus())
  }

  const submit = async (event) => {
    event.preventDefault()
    if (inFlight.current) return // ignore double clicks while a request is out

    const found = validate(form, config, slots)
    if (Object.keys(found).length) {
      showErrors(found)
      return
    }

    inFlight.current = true
    setStatus('submitting')
    setFailure('')
    try {
      const data = await api('/bookings', {
        method: 'POST',
        body: {
          full_name: form.full_name.trim(),
          phone: fullPhone(form),
          email: form.email.trim() || null,
          requested_date: form.requested_date,
          requested_time: form.requested_time,
          party_size: Number(form.party_size),
          special_requests: form.special_requests.trim() || null,
          idempotency_key: idempotencyKey.current,
        },
      })
      // Success is only ever shown from a stored booking returned by the server.
      setReceipt({ ...data, summary: { ...form } })
      setStatus('success')
      setForm(EMPTY)
      idempotencyKey.current = newKey()
      requestAnimationFrame(() => successRef.current?.focus())
    } catch (err) {
      setStatus('error')
      const fieldErrors = Object.fromEntries(Object.entries(err.fields || {}).filter(([k]) => k in EMPTY || k === 'phone'))
      if (Object.keys(fieldErrors).length) {
        setFailure('Your request was not sent. Please check the highlighted details.')
        showErrors(fieldErrors)
      } else {
        setFailure(
          err.code === 'rate_limited' || err.code === 'booking_unavailable'
            ? `Your request was not sent. ${err.message}`
            : `Your request was not sent. ${err.message} If it keeps happening, call us on ${BUSINESS.phoneDisplay}.`,
        )
      }
      if (err.code === 'booking_unavailable') loadConfig()
    } finally {
      inFlight.current = false
    }
  }

  const submitting = status === 'submitting'
  const describe = (name) => (errors[name] ? `${name}-error` : undefined)
  const FieldError = ({ name }) =>
    errors[name] ? (
      <p id={`${name}-error`} className="field-error">
        {errors[name]}
      </p>
    ) : null

  return (
    <section id="book" className="section grid gap-10 bg-sage lg:grid-cols-[1fr_1.15fr] lg:gap-[7%]">
      <Reveal>
        <p className="eyebrow">Save a seat</p>
        <h2 className="h2">
          A table,
          <br />
          <em>whenever you’re ready.</em>
        </h2>
        <p className="my-[26px] max-w-[440px] leading-[1.85]">
          Tell us when you’d like to come and how many of you there are. We’ll check our tables and get back to you.
        </p>
        <ol className="max-w-[440px] space-y-4 text-sm leading-[1.7]">
          {[
            ['Send a request', 'It takes a minute. This is a request, not an instant booking.'],
            ['We check availability', 'The team looks at the day and your group size.'],
            ['We contact you', 'By phone or message, to confirm or suggest another time. Your table is only confirmed once you hear from us.'],
          ].map(([title, text], i) => (
            <li key={title} className="flex gap-4">
              <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-forest font-display text-base">
                {i + 1}
              </span>
              <span>
                <strong className="block">{title}</strong>
                {text}
              </span>
            </li>
          ))}
        </ol>
        <div className="mt-7 max-w-[440px] text-sm">
          <p>Coming right now, in a bigger group, or need a hand with this form?</p>
          <p className="mt-3 flex flex-wrap gap-3">
            <a className="pill !py-2" href={BUSINESS.phoneHref}>
              Call {BUSINESS.phoneDisplay}
            </a>
            <a className="pill !py-2" href={BUSINESS.whatsappUrl} target="_blank" rel="noopener noreferrer">
              WhatsApp us<span className="sr-only"> (opens in a new tab)</span>
            </a>
          </p>
          <p className="mt-3 text-xs opacity-75">
            WhatsApp opens a chat with the shop. A message there is not a table request and does not confirm a booking.
          </p>
        </div>
      </Reveal>

      <Reveal className="rounded-[20px] bg-cream p-6 md:p-10">
        {configState === 'loading' && (
          <p role="status" className="py-10 text-sm">
            Loading the request form…
          </p>
        )}

        {configState === 'error' && (
          <div role="alert">
            <h3 className="text-[26px] tracking-[-0.6px]">The request form isn’t available right now.</h3>
            <p className="my-4 text-sm leading-[1.8]">
              We couldn’t load it, so nothing has been sent. Please try again, or call us on{' '}
              <a className="font-semibold underline" href={BUSINESS.phoneHref}>
                {BUSINESS.phoneDisplay}
              </a>
              .
            </p>
            <button type="button" className="pill" onClick={loadConfig}>
              Try again
            </button>
          </div>
        )}

        {configState === 'ready' && !config.accepting_requests && status !== 'success' && (
          <div>
            <h3 className="text-[26px] tracking-[-0.6px]">Online table requests are paused.</h3>
            <p className="my-4 text-sm leading-[1.8]">
              Please call us on{' '}
              <a className="font-semibold underline" href={BUSINESS.phoneHref}>
                {BUSINESS.phoneDisplay}
              </a>{' '}
              and we’ll happily find you a spot.
            </p>
          </div>
        )}

        {status === 'success' && receipt && (
          <div role="status" aria-live="polite">
            <p className="eyebrow">Request received · not yet confirmed</p>
            <h3 ref={successRef} tabIndex={-1} className="text-[30px] tracking-[-0.8px] outline-none md:text-[36px]">
              Thank you, we’ve got it.
            </h3>
            <p className="my-5 rounded-lg border border-forest/25 bg-citrus/50 p-4 font-medium leading-[1.7]">{receipt.message}</p>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="opacity-70">Reference</dt>
              <dd className="font-semibold tracking-[1px]">{receipt.reference}</dd>
              <dt className="opacity-70">Requested for</dt>
              <dd>
                {formatDate(receipt.summary.requested_date)}, {formatTime(receipt.summary.requested_time)} (Pokhara time)
              </dd>
              <dt className="opacity-70">Guests</dt>
              <dd>{receipt.summary.party_size}</dd>
              <dt className="opacity-70">Status</dt>
              <dd>Pending — waiting for the team to check</dd>
            </dl>
            <p className="my-5 text-sm leading-[1.7]">
              Keep your reference handy. No confirmation message has been sent automatically; the team will reach you on
              the number you gave. Need to change something? Call{' '}
              <a className="font-semibold underline" href={BUSINESS.phoneHref}>
                {BUSINESS.phoneDisplay}
              </a>
              .
            </p>
            <button
              type="button"
              className="pill"
              onClick={() => {
                setStatus('idle')
                setReceipt(null)
              }}
            >
              Make another request
            </button>
          </div>
        )}

        {configState === 'ready' && config.accepting_requests && status !== 'success' && (
          <form ref={formRef} onSubmit={submit} noValidate aria-busy={submitting} aria-labelledby="book-form-title">
            <h3 id="book-form-title" className="mb-1 text-[26px] tracking-[-0.6px]">
              Request a table
            </h3>
            <p className="mb-6 text-sm opacity-75">Times are Pokhara time (Asia/Kathmandu). Fields marked * are needed.</p>

            {status === 'error' && failure && (
              <p role="alert" className="mb-6 rounded-lg border border-berry/40 bg-berry/5 p-4 text-sm font-medium text-berry">
                {failure}
              </p>
            )}

            <fieldset disabled={submitting} className="grid gap-5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="full_name">
                  Full name *
                </label>
                <input
                  id="full_name"
                  name="full_name"
                  className="field"
                  autoComplete="name"
                  maxLength={120}
                  required
                  value={form.full_name}
                  onChange={update('full_name')}
                  aria-invalid={Boolean(errors.full_name)}
                  aria-describedby={describe('full_name')}
                />
                <FieldError name="full_name" />
              </div>

              <div className="sm:col-span-2">
                <span className="field-label" id="phone-label">
                  Phone, with country code *
                </span>
                <div className="flex flex-wrap gap-2" role="group" aria-labelledby="phone-label">
                  <select
                    name="country_code"
                    aria-label="Country code"
                    className="field !w-auto max-w-[190px] flex-none"
                    autoComplete="tel-country-code"
                    value={form.country_code}
                    onChange={update('country_code')}
                  >
                    {COUNTRY_CODES.map(([code, country]) => (
                      <option key={country} value={code}>
                        {country} ({code})
                      </option>
                    ))}
                    <option value="other">Other country…</option>
                  </select>
                  {form.country_code === 'other' && (
                    <input
                      name="custom_code"
                      aria-label="Your country code"
                      className="field !w-[92px] flex-none"
                      inputMode="tel"
                      placeholder="+46"
                      maxLength={5}
                      value={form.custom_code}
                      onChange={update('custom_code')}
                      aria-invalid={Boolean(errors.phone)}
                    />
                  )}
                  <input
                    name="phone_number"
                    aria-label="Phone number"
                    className="field min-w-[150px] flex-1"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel-national"
                    placeholder="98XXXXXXXX"
                    maxLength={20}
                    required
                    value={form.phone_number}
                    onChange={update('phone_number')}
                    aria-invalid={Boolean(errors.phone)}
                    aria-describedby={describe('phone')}
                  />
                </div>
                <FieldError name="phone" />
              </div>

              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="email">
                  Email <span className="normal-case tracking-normal opacity-70">(optional)</span>
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  className="field"
                  autoComplete="email"
                  maxLength={254}
                  value={form.email}
                  onChange={update('email')}
                  aria-invalid={Boolean(errors.email)}
                  aria-describedby={describe('email')}
                />
                <FieldError name="email" />
              </div>

              <div>
                <label className="field-label" htmlFor="requested_date">
                  Date *
                </label>
                <input
                  id="requested_date"
                  name="requested_date"
                  type="date"
                  className="field"
                  required
                  min={config.today}
                  max={addDays(config.today, config.max_advance_days)}
                  value={form.requested_date}
                  onChange={update('requested_date')}
                  aria-invalid={Boolean(errors.requested_date)}
                  aria-describedby={describe('requested_date')}
                />
                <FieldError name="requested_date" />
              </div>

              <div>
                <label className="field-label" htmlFor="requested_time">
                  Time *
                </label>
                <select
                  id="requested_time"
                  name="requested_time"
                  className="field"
                  required
                  disabled={!form.requested_date || slots.length === 0}
                  value={form.requested_time}
                  onChange={update('requested_time')}
                  aria-invalid={Boolean(errors.requested_time)}
                  aria-describedby={describe('requested_time') || 'time-hint'}
                >
                  <option value="">
                    {!form.requested_date ? 'Pick a date first' : slots.length ? 'Choose a time' : 'No times this day'}
                  </option>
                  {slots.map((slot) => (
                    <option key={slot} value={slot}>
                      {formatTime(slot)}
                    </option>
                  ))}
                </select>
                <FieldError name="requested_time" />
              </div>

              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="party_size">
                  Number of guests *
                </label>
                <select
                  id="party_size"
                  name="party_size"
                  className="field sm:!w-1/2"
                  required
                  value={form.party_size}
                  onChange={update('party_size')}
                  aria-invalid={Boolean(errors.party_size)}
                  aria-describedby={describe('party_size')}
                >
                  {Array.from({ length: config.max_party_size - config.min_party_size + 1 }, (_, i) => config.min_party_size + i).map((n) => (
                    <option key={n} value={n}>
                      {n} {n === 1 ? 'guest' : 'guests'}
                    </option>
                  ))}
                </select>
                <FieldError name="party_size" />
              </div>

              <div className="sm:col-span-2">
                <label className="field-label" htmlFor="special_requests">
                  Special requests <span className="normal-case tracking-normal opacity-70">(optional)</span>
                </label>
                <textarea
                  id="special_requests"
                  name="special_requests"
                  rows={3}
                  className="field"
                  maxLength={1000}
                  placeholder="High chair, allergies, a quiet corner…"
                  value={form.special_requests}
                  onChange={update('special_requests')}
                  aria-invalid={Boolean(errors.special_requests)}
                  aria-describedby={describe('special_requests')}
                />
                <FieldError name="special_requests" />
              </div>
            </fieldset>

            <p id="time-hint" className="mt-5 text-xs leading-[1.7] opacity-75">
              The times listed are when requests can be made for, not a promise that a table is free.
            </p>
            <p className="mt-2 text-xs leading-[1.7] opacity-75">
              <strong>Privacy:</strong> we collect your name, phone number and optional email only so the Wendy team can
              reply to this request and look after your visit. They are not used for marketing or shared with anyone
              else. To have your details removed, call or email us.
            </p>

            <button type="submit" className="pill pill-dark mt-6 w-full sm:w-auto" disabled={submitting}>
              {submitting ? 'Sending your request…' : 'Send table request'}
            </button>
            <p role="status" aria-live="polite" className="sr-only">
              {submitting ? 'Sending your request.' : ''}
            </p>
          </form>
        )}
      </Reveal>
    </section>
  )
}

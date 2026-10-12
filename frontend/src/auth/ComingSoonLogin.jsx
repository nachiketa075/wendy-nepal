import { Link } from 'react-router-dom'
import { BUSINESS } from '../lib/business.js'
import { PREVIEW_ENABLED } from '../lib/preview.js'
import { AreaShell, LoginCard } from './AuthLayout.jsx'

const COPY = {
  customer: {
    tagline: 'CUSTOMER SIGN-IN',
    eyebrow: 'For guests',
    path: '/customer/login',
    previewPath: '/customer',
    notice:
      'Customer accounts are not switched on yet, so there is nothing to sign in to. You don’t need an account to ask for a table.',
  },
  employee: {
    tagline: 'STAFF SIGN-IN',
    eyebrow: 'For the Wendy team',
    path: '/employee/login',
    previewPath: '/employee',
    notice: 'Staff accounts are not switched on yet, so signing in here is not possible. Please ask the owner if you need access to bookings.',
  },
}

/**
 * Sign-in page for an area whose backend does not exist yet.
 * The form is shown for design review but is disabled: it submits nowhere,
 * accepts no credentials and stores nothing.
 */
export default function ComingSoonLogin({ area }) {
  const copy = COPY[area]
  return (
    <AreaShell tagline={copy.tagline} title={`${area === 'customer' ? 'Customer' : 'Staff'} sign-in`}>
      <LoginCard eyebrow={copy.eyebrow} title="Sign in" current={copy.path}>
        <p role="status" className="mb-6 rounded-lg border border-amber bg-citrus/40 p-4 text-sm leading-[1.7]">
          <strong>Sign-in is not available yet.</strong> {copy.notice}
        </p>

        <form onSubmit={(e) => e.preventDefault()} aria-describedby={`${area}-disabled-note`} noValidate>
          <fieldset disabled className="opacity-55">
            <label className="field-label" htmlFor={`${area}-email`}>
              Email
            </label>
            <input id={`${area}-email`} type="email" className="field mb-5" autoComplete="off" />
            <label className="field-label" htmlFor={`${area}-password`}>
              Password
            </label>
            <input id={`${area}-password`} type="password" className="field mb-6" autoComplete="off" />
            <button type="submit" className="pill pill-dark w-full">
              Sign in
            </button>
          </fieldset>
          <p id={`${area}-disabled-note`} className="mt-3 text-center text-xs opacity-75">
            This form is switched off and does not send anything.
          </p>
        </form>

        {area === 'customer' && (
          <div className="mt-6 border-t border-forest/20 pt-5 text-sm">
            <p className="mb-3 font-semibold">Want a table?</p>
            <div className="flex flex-wrap gap-2">
              <a className="pill pill-dark !py-2" href="/#book">
                Request a table
              </a>
              <a className="pill !py-2" href={BUSINESS.phoneHref}>
                Call
              </a>
              <a className="pill !py-2" href={BUSINESS.whatsappUrl} target="_blank" rel="noopener noreferrer">
                WhatsApp<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </div>
          </div>
        )}

        {PREVIEW_ENABLED && (
          <div className="mt-6 border-t border-forest/20 pt-5 text-sm">
            <p className="mb-3">
              <strong>Developer preview is on.</strong> You can look at the planned screens with fictional data. This is not
              a sign-in and shows no real bookings.
            </p>
            <Link className="pill !py-2" to={copy.previewPath}>
              Open the design preview
            </Link>
          </div>
        )}
      </LoginCard>
    </AreaShell>
  )
}

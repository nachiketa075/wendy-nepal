import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import { ForgotPage, LoginPage, RegisterPage, ResetPage } from './auth/AccountPages.jsx'
import { SessionProvider } from './lib/session.jsx'
import MenuPage from './site/MenuPage.jsx'
import SitePage from './site/SitePage.jsx'

const StaffApp = React.lazy(() => import('./staff/StaffApp.jsx'))
const CustomerApp = React.lazy(() => import('./customer/CustomerApp.jsx'))

const lazyPage = (element) => <React.Suspense fallback={<p className="p-10">Loading…</p>}>{element}</React.Suspense>

// Three separate sign-in pages share one sign-in service. Which page was used
// never decides the role: the server reports it, and each area below checks it.
createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <Routes>
          <Route path="/owner/login" element={<LoginPage portal="owner" />} />
          <Route path="/owner/*" element={lazyPage(<StaffApp portal="owner" />)} />

          <Route path="/employee/login" element={<LoginPage portal="employee" />} />
          <Route path="/employee/*" element={lazyPage(<StaffApp portal="employee" />)} />

          <Route path="/customer/login" element={<LoginPage portal="customer" />} />
          <Route path="/customer/register" element={<RegisterPage />} />
          <Route path="/customer/*" element={lazyPage(<CustomerApp />)} />

          <Route path="/account/forgot" element={<ForgotPage />} />
          <Route path="/account/reset" element={<ResetPage />} />

          <Route path="/menu" element={<MenuPage />} />
          <Route path="*" element={<SitePage />} />
        </Routes>
      </SessionProvider>
    </BrowserRouter>
  </React.StrictMode>,
)

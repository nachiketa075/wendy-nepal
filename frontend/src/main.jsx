import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './index.css'
import ComingSoonLogin from './auth/ComingSoonLogin.jsx'
import { PREVIEW_ENABLED } from './lib/preview.js'
import MenuPage from './site/MenuPage.jsx'
import SitePage from './site/SitePage.jsx'

const OwnerApp = React.lazy(() => import('./owner/OwnerApp.jsx'))

// Customer and employee areas have no backend yet. Their screens exist only as a
// development preview with fictional data; in a normal build these imports are
// never created and the routes send visitors to the (disabled) sign-in pages.
const CustomerPreview = PREVIEW_ENABLED ? React.lazy(() => import('./preview/CustomerPreview.jsx')) : null
const EmployeePreview = PREVIEW_ENABLED ? React.lazy(() => import('./preview/EmployeePreview.jsx')) : null

const lazyPage = (Page) => (
  <React.Suspense fallback={<p className="p-10">Loading…</p>}>
    <Page />
  </React.Suspense>
)

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* /owner and /owner/login share the existing, real owner session. */}
        <Route path="/owner/*" element={lazyPage(OwnerApp)} />

        <Route path="/customer/login" element={<ComingSoonLogin area="customer" />} />
        <Route path="/customer/*" element={CustomerPreview ? lazyPage(CustomerPreview) : <Navigate to="/customer/login" replace />} />

        <Route path="/employee/login" element={<ComingSoonLogin area="employee" />} />
        <Route path="/employee/*" element={EmployeePreview ? lazyPage(EmployeePreview) : <Navigate to="/employee/login" replace />} />

        <Route path="/menu" element={<MenuPage />} />
        <Route path="*" element={<SitePage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)

import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import './index.css'
import SitePage from './site/SitePage.jsx'

const OwnerApp = React.lazy(() => import('./owner/OwnerApp.jsx'))

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route
          path="/owner/*"
          element={
            <React.Suspense fallback={<p className="p-10">Loading…</p>}>
              <OwnerApp />
            </React.Suspense>
          }
        />
        <Route path="*" element={<SitePage />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)

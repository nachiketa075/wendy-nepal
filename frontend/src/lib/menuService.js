// Single place the public menu is loaded from.
//
//   'pdf' (default for this phase) - the owner's printed menu in src/data/menuFromPdf.js
//   'api'                          - GET /api/menu, the database menu the owner dashboard edits
//
// Set VITE_MENU_SOURCE=api to switch back once the PDF menu has been imported
// into the database (see docs/API_HANDOFF.md). There is deliberately no fallback
// from one source to the other: if the chosen source fails, the caller shows an
// error instead of quietly displaying a different, possibly stale, menu.
import { api } from './api.js'

export const MENU_SOURCE = import.meta.env.VITE_MENU_SOURCE === 'api' ? 'api' : 'pdf'

/** Resolves to { source, categories } in the GET /api/menu shape. */
export async function loadMenu({ signal } = {}) {
  if (MENU_SOURCE === 'api') {
    const data = await api('/menu', { signal })
    return { source: 'api', categories: data.categories.map((c) => ({ notes: [], ...c, items: c.items.map((i) => ({ addons: [], ...i })) })) }
  }
  const { PDF_MENU } = await import('../data/menuFromPdf.js')
  return { source: 'pdf', categories: PDF_MENU.categories }
}

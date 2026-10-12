// The public menu comes from the database through GET /api/menu: the same rows
// the staff menu editor changes. There is no bundled copy to fall back to; if
// the request fails, the caller shows an error.
import { api } from './api.js'

/** Resolves to { categories } with addons/notes always present as arrays. */
export async function loadMenu({ signal } = {}) {
  const data = await api('/menu', { signal })
  return {
    categories: data.categories.map((c) => ({ ...c, notes: c.notes || [], items: c.items.map((i) => ({ ...i, addons: i.addons || [] })) })),
  }
}

import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'

const SOURCE_NOTE = {
  listing: 'From a public listing — please check it is right.',
  menu_photo: 'Read from a guest photo of the menu board — please check it is still on the menu.',
  owner: 'Added by you.',
}

export default function MenuPanel({ onAuthError }) {
  const [categories, setCategories] = useState(null)
  const [error, setError] = useState('')
  const [newCategory, setNewCategory] = useState('')

  const load = useCallback(async () => {
    try {
      setCategories((await api('/owner/menu')).categories)
    } catch (err) {
      if (!onAuthError(err)) setError(err.message)
    }
  }, [onAuthError])

  useEffect(() => {
    load()
  }, [load])

  // Runs a change, reloads the menu, and reports any failure. Returns true on success.
  const run = useCallback(
    async (request) => {
      setError('')
      try {
        await request()
        await load()
        return true
      } catch (err) {
        if (!onAuthError(err)) setError(Object.values(err.fields || {})[0] || err.message)
        return false
      }
    },
    [load, onAuthError],
  )

  const addCategory = async (event) => {
    event.preventDefault()
    if (!newCategory.trim()) return
    const sort_order = Math.max(0, ...(categories || []).map((c) => c.sort_order)) + 10
    if (await run(() => api('/owner/menu/categories', { method: 'POST', body: { name: newCategory, sort_order } }))) setNewCategory('')
  }

  if (!categories) return <p role={error ? 'alert' : 'status'}>{error || 'Loading menu…'}</p>

  return (
    <section aria-labelledby="menu-title">
      <h1 id="menu-title" className="mb-2 text-[40px]">
        Menu
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        Changes appear on the website as soon as you save. A price is only shown to guests when you enter one here, and
        is displayed in NPR. Leave it empty to show no price.
      </p>
      {error && (
        <p role="alert" className="sticky top-2 z-10 mb-5 rounded-lg border border-berry/40 bg-cream p-3 text-sm font-medium text-berry">
          {error}
        </p>
      )}

      {categories.map((category) => (
        <CategoryBlock key={category.id} category={category} categories={categories} run={run} />
      ))}

      <form onSubmit={addCategory} className="mt-10 flex flex-wrap items-end gap-3 rounded-[5px] bg-sage p-5">
        <label className="flex-1">
          <span className="field-label">New category</span>
          <input className="field" maxLength={80} value={newCategory} onChange={(e) => setNewCategory(e.target.value)} placeholder="Seasonal specials" />
        </label>
        <button type="submit" className="pill">
          Add category
        </button>
      </form>
    </section>
  )
}

function CategoryBlock({ category, categories, run }) {
  const [name, setName] = useState(category.name)
  const [tagline, setTagline] = useState(category.tagline || '')
  const dirty = name !== category.name || tagline !== (category.tagline || '')
  const nextOrder = Math.max(0, ...category.items.map((i) => i.sort_order)) + 10

  return (
    <div className="mb-10">
      <div className="mb-4 flex flex-wrap items-end gap-3 border-b border-forest pb-4">
        <label className="min-w-[200px] flex-1">
          <span className="field-label">Category name</span>
          <input className="field font-display !text-xl" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="min-w-[200px] flex-1">
          <span className="field-label">Small label above items</span>
          <input className="field" maxLength={80} value={tagline} onChange={(e) => setTagline(e.target.value)} />
        </label>
        <button
          type="button"
          className="pill !py-2"
          disabled={!dirty || !name.trim()}
          onClick={() => run(() => api(`/owner/menu/categories/${category.id}`, { method: 'PATCH', body: { name, tagline } }))}
        >
          Save
        </button>
        <button
          type="button"
          className="textlink mb-2"
          onClick={() =>
            window.confirm(`Delete the category “${category.name}”? It must be empty.`) &&
            run(() => api(`/owner/menu/categories/${category.id}`, { method: 'DELETE' }))
          }
        >
          Delete category
        </button>
      </div>

      <ul className="grid gap-4 lg:grid-cols-2">
        {category.items.map((item) => (
          <ItemForm key={item.id} item={item} categories={categories} run={run} />
        ))}
        <ItemForm key={`new-${category.items.length}`} item={{ category_id: category.id, name: '', description: '', is_available: true, price_npr: null, sort_order: nextOrder }} categories={categories} run={run} />
      </ul>
    </div>
  )
}

function ItemForm({ item, categories, run }) {
  const isNew = item.id === undefined
  const initial = {
    name: item.name,
    description: item.description || '',
    category_id: String(item.category_id),
    is_available: item.is_available,
    price_npr: item.price_npr === null ? '' : String(Number(item.price_npr)),
  }
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const dirty = JSON.stringify(form) !== JSON.stringify(initial)
  const set = (name) => (e) => {
    setSaved(false)
    setForm((f) => ({ ...f, [name]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  }

  const save = async (event) => {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    const body = {
      name: form.name,
      description: form.description,
      category_id: Number(form.category_id),
      is_available: form.is_available,
      price_npr: form.price_npr === '' ? null : form.price_npr,
    }
    const ok = await run(() =>
      isNew
        ? api('/owner/menu/items', { method: 'POST', body: { ...body, sort_order: item.sort_order } })
        : api(`/owner/menu/items/${item.id}`, { method: 'PATCH', body }),
    )
    setBusy(false)
    setSaved(ok)
  }

  const uid = isNew ? `new-${item.category_id}` : item.id
  return (
    <li className={`rounded-[5px] border p-4 ${isNew ? 'border-dashed border-forest/50' : 'border-line bg-white/60'}`}>
      <form onSubmit={save} className="grid gap-3 sm:grid-cols-[1fr_130px]" aria-label={isNew ? 'Add a menu item' : `Edit ${item.name}`}>
        <label>
          <span className="field-label">{isNew ? 'New item name' : 'Name'}</span>
          <input className="field !py-2" required maxLength={120} value={form.name} onChange={set('name')} />
        </label>
        <label>
          <span className="field-label">Price (NPR)</span>
          <input className="field !py-2" type="number" min="0" step="0.01" inputMode="decimal" placeholder="none" value={form.price_npr} onChange={set('price_npr')} />
        </label>
        <label className="sm:col-span-2">
          <span className="field-label">Description</span>
          <textarea className="field !py-2 text-sm" rows={2} maxLength={600} value={form.description} onChange={set('description')} />
        </label>
        <label>
          <span className="field-label">Category</span>
          <select className="field !py-2" value={form.category_id} onChange={set('category_id')}>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input id={`avail-${uid}`} type="checkbox" className="h-5 w-5 accent-forest" checked={form.is_available} onChange={set('is_available')} />
          Available
        </label>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button type="submit" className="pill !py-2" disabled={busy || !dirty || !form.name.trim()}>
            {busy ? 'Saving…' : isNew ? 'Add item' : 'Save'}
          </button>
          {!isNew && (
            <button
              type="button"
              className="textlink"
              onClick={() => window.confirm(`Remove “${item.name}” from the menu?`) && run(() => api(`/owner/menu/items/${item.id}`, { method: 'DELETE' }))}
            >
              Remove
            </button>
          )}
          <span role="status" className="text-sm font-medium">
            {saved && !dirty ? 'Saved.' : ''}
          </span>
          {!isNew && <span className="text-xs opacity-65">{SOURCE_NOTE[item.source]}</span>}
        </div>
      </form>
    </li>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api.js'

const SOURCE_NOTE = {
  listing: 'Older item from a public listing.',
  menu_photo: 'Older item read from a photo of the menu board.',
  owner: 'Added in this dashboard.',
  owner_pdf: 'From your printed menu.',
}

// Add-ons are edited one per line: "label | price | unit", e.g. "add on 2 eggs | 80".
const addonsToText = (addons) => (addons || []).map((a) => [a.label, a.price, a.unit].filter((v) => v !== undefined && v !== null && v !== '').join(' | ')).join('\n')
function textToAddons(text, keep = []) {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [label = '', price = '', unit = ''] = line.split('|').map((part) => part.trim())
      const previous = keep.find((a) => a.label === label)
      return { label, price, ...(unit ? { unit } : {}), ...(previous?.prefix ? { prefix: previous.prefix } : {}) }
    })
}

export default function MenuPanel({ onAuthError }) {
  const [categories, setCategories] = useState(null)
  const [error, setError] = useState('')
  const [newCategory, setNewCategory] = useState('')

  const load = useCallback(async () => {
    try {
      setCategories((await api('/staff/menu')).categories)
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
    if (await run(() => api('/staff/menu/categories', { method: 'POST', body: { name: newCategory, sort_order } }))) setNewCategory('')
  }

  if (!categories) return <p role={error ? 'alert' : 'status'}>{error || 'Loading menu…'}</p>

  return (
    <section aria-labelledby="menu-title">
      <h1 id="menu-title" className="mb-2 text-[40px]">
        Menu
      </h1>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        This is the menu guests see on the website: changes appear as soon as you save. Untick “Show on website” to hide an
        item without deleting it. Prices are shown as “Rs.”; leave a price empty to show none.
      </p>
      {error && (
        <p role="alert" className="sticky top-2 z-10 mb-5 rounded-lg border border-berry/40 bg-cream p-3 text-sm font-medium text-berry">
          {error}
        </p>
      )}

      {categories.map((category) => (
        <CategoryBlock key={category.id} category={category} categories={categories} run={run} />
      ))}

      <form onSubmit={addCategory} className="mt-10 flex flex-wrap items-end gap-3 rounded-[20px] bg-sage p-5">
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
  const [notes, setNotes] = useState(addonsToText(category.notes))
  const dirty = name !== category.name || tagline !== (category.tagline || '') || notes !== addonsToText(category.notes)
  const nextOrder = Math.max(0, ...category.items.map((i) => i.sort_order)) + 10

  return (
    <div className="mb-10">
      <div className="mb-4 flex flex-wrap items-end gap-3 border-b border-forest pb-4">
        <label className="min-w-[200px] flex-1">
          <span className="field-label">Category name</span>
          <input className="field font-display !text-xl" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="min-w-[200px] flex-1">
          <span className="field-label">Section extras (label | price)</span>
          <input className="field" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Extra Cheese Topping | 70" />
        </label>
        <button
          type="button"
          className="pill !py-2"
          disabled={!dirty || !name.trim()}
          onClick={() => run(() => api(`/staff/menu/categories/${category.id}`, { method: 'PATCH', body: { name, tagline, notes: textToAddons(notes, category.notes) } }))}
        >
          Save
        </button>
        <button
          type="button"
          className="textlink mb-2"
          onClick={() =>
            window.confirm(`Delete the category “${category.name}”? It must be empty.`) &&
            run(() => api(`/staff/menu/categories/${category.id}`, { method: 'DELETE' }))
          }
        >
          Delete category
        </button>
      </div>

      <ul className="grid gap-4 lg:grid-cols-2">
        {category.items.map((item) => (
          <ItemForm key={item.id} item={item} categories={categories} run={run} />
        ))}
        <ItemForm key={`new-${category.items.length}`} item={{ category_id: category.id, name: '', description: '', is_available: true, is_published: true, addons: [], price_npr: null, sort_order: nextOrder }} categories={categories} run={run} />
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
    is_published: item.is_published,
    addons: addonsToText(item.addons),
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
      is_published: form.is_published,
      addons: textToAddons(form.addons, item.addons),
      price_npr: form.price_npr === '' ? null : form.price_npr,
    }
    const ok = await run(() =>
      isNew
        ? api('/staff/menu/items', { method: 'POST', body: { ...body, sort_order: item.sort_order } })
        : api(`/staff/menu/items/${item.id}`, { method: 'PATCH', body }),
    )
    setBusy(false)
    setSaved(ok)
  }

  const uid = isNew ? `new-${item.category_id}` : item.id
  return (
    <li className={`rounded-[20px] border p-4 ${isNew ? 'border-dashed border-forest/50' : 'border-line bg-white/60'} ${!isNew && !item.is_published ? 'opacity-70' : ''}`}>
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
        <label className="sm:col-span-2">
          <span className="field-label">
            Add-ons <span className="normal-case tracking-normal opacity-70">(one per line: label | price | unit)</span>
          </span>
          <textarea className="field !py-2 text-sm" rows={form.addons ? 2 : 1} value={form.addons} onChange={set('addons')} placeholder="add on 2 eggs | 80" />
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
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="h-5 w-5 accent-forest" checked={form.is_published} onChange={set('is_published')} />
          Show on website
        </label>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button type="submit" className="pill !py-2" disabled={busy || !dirty || !form.name.trim()}>
            {busy ? 'Saving…' : isNew ? 'Add item' : 'Save'}
          </button>
          {!isNew && (
            <button
              type="button"
              className="textlink"
              onClick={() => window.confirm(`Remove “${item.name}” from the menu?`) && run(() => api(`/staff/menu/items/${item.id}`, { method: 'DELETE' }))}
            >
              Remove
            </button>
          )}
          <span role="status" className="text-sm font-medium">
            {saved && !dirty ? 'Saved.' : ''}
          </span>
          {!isNew && (
            <span className="text-xs opacity-65">
              {SOURCE_NOTE[item.source]}
              {item.edited_since_import ? ' Edited by you since the import.' : ''}
            </span>
          )}
          {!isNew && item.review_note && <span className="w-full rounded-lg bg-citrus/50 px-3 py-2 text-xs">Please check: {item.review_note}</span>}
        </div>
      </form>
    </li>
  )
}

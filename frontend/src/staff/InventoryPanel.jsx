import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../lib/api.js'
import { useSession } from '../lib/session.jsx'
import { formatDateTime } from '../lib/time.js'

export const CATEGORIES = [
  ['fruit_veg', 'Fruit & vegetables'],
  ['dairy', 'Milk & dairy'],
  ['coffee_tea', 'Coffee & tea'],
  ['dry_goods', 'Dry goods'],
  ['packaging', 'Cups & packaging'],
  ['cleaning', 'Cleaning & supplies'],
  ['other', 'Other'],
]
const CATEGORY_LABEL = Object.fromEntries(CATEGORIES)
const UNITS = [
  ['kg', 'Kilograms (kg)'],
  ['litre', 'Litres (L)'],
  ['piece', 'Pieces (pcs)'],
]
const UNIT_SHORT = { kg: 'kg', litre: 'L', piece: 'pcs' }
const KIND_LABEL = { opening: 'Opening stock', stock_in: 'Stock in', stock_out: 'Stock out', adjustment: 'Correction' }
const PAGE = 50
const HISTORY_PAGE = 20

const newKey = () =>
  window.crypto?.randomUUID?.().replaceAll('-', '') ??
  `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`

const qty = (value, unit) => `${value} ${UNIT_SHORT[unit]}`
const signed = (value) => (value.startsWith('-') ? `−${value.slice(1)}` : value === '0' ? '±0' : `+${value}`)

/** Client-side check only, for a quick hint; the server validates again. */
function quantityProblem(text, unit, { allowZero = true, required = true } = {}) {
  const value = text.trim()
  if (!value) return required ? 'Enter a quantity.' : ''
  if (!/^\d+(\.\d{1,3})?$/.test(value)) return 'Use a number like 2 or 2.5 (up to 3 decimal places).'
  if (unit === 'piece' && Number(value) % 1 !== 0) return 'Pieces need a whole number.'
  if (!allowZero && Number(value) === 0) return 'Enter an amount more than 0.'
  return ''
}

function LowBadge({ item }) {
  if (!item.is_active) return <span className="rounded-full bg-line px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[1.2px]">Archived</span>
  if (!item.is_low) return null
  return (
    <span className="rounded-full bg-berry px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-[1.2px] text-cream">
      {item.quantity === '0' ? 'Out of stock' : 'Low stock'}
    </span>
  )
}

// A lost connection or a server error leaves it unknown whether the entry was
// saved. The form keeps its idempotency key until something is changed, so
// sending the same thing again is safe: the server records it at most once.
const UNCERTAIN =
  'The server did not confirm this, so it may or may not have been recorded. Press the button again without changing anything: the same entry is never recorded twice.'
const isUncertain = (err) => err.status === 0 || err.status >= 500

function Message({ message }) {
  return (
    <p role={message && !message.ok ? 'alert' : 'status'} className={`min-h-5 text-sm font-medium ${message && !message.ok ? 'text-berry' : ''}`}>
      {message?.text}
    </p>
  )
}

/** Staff inventory: items, stock levels and their history. Needs inventory.view. */
export default function InventoryPanel({ onLowCount }) {
  const { can, handleAuthError } = useSession()
  const canManage = can('inventory.manage_items')
  const canAdjust = can('inventory.adjust_stock')

  const [filters, setFilters] = useState({ search: '', category: '', status: 'active', low_stock: false })
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selected, setSelected] = useState(null)
  const [adding, setAdding] = useState(false)
  const [historyKey, setHistoryKey] = useState(0)
  const detailRef = useRef(null)

  // Wait for a pause in typing before searching.
  useEffect(() => {
    const timer = setTimeout(() => {
      setOffset(0)
      setFilters((f) => (f.search === search.trim() ? f : { ...f, search: search.trim() }))
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams([
      ...Object.entries(filters).filter(([, v]) => v !== '' && v !== false),
      ['limit', PAGE],
      ['offset', offset],
    ])
    try {
      const result = await api(`/staff/inventory/items?${params}`)
      setData(result)
      onLowCount?.(result.low_stock_count)
    } catch (err) {
      if (!handleAuthError(err)) setError(err.status === 403 ? 'You no longer have permission to view inventory.' : err.message)
    } finally {
      setLoading(false)
    }
  }, [filters, offset, handleAuthError, onLowCount])

  useEffect(() => {
    load()
  }, [load])

  const setFilter = (name, value) => {
    setOffset(0)
    setFilters((f) => ({ ...f, [name]: value }))
  }

  const changed = useCallback(async () => {
    setHistoryKey((k) => k + 1)
    await load()
  }, [load])

  const open = (id) => {
    setSelected(id)
    setAdding(false)
    requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }

  const filtered = filters.search || filters.category || filters.low_stock || filters.status !== 'active'

  return (
    <section aria-labelledby="inventory-title">
      <div className="mb-2 flex flex-wrap items-end justify-between gap-4">
        <h1 id="inventory-title" className="text-[40px]">
          Inventory
        </h1>
        {canManage && !adding && (
          <button type="button" className="pill pill-dark !py-2" onClick={() => { setAdding(true); setSelected(null) }}>
            Add item
          </button>
        )}
      </div>
      <p className="mb-6 max-w-2xl text-sm opacity-80">
        Stock the shop keeps: fruit, milk, coffee, cups and supplies. Only staff with inventory access see this page.
        Stock changes only through a recorded entry (stock in, stock out or a correction), so the history always adds up.
        Nothing here is shown on the website or linked to the menu.
      </p>

      {data?.low_stock_count > 0 && (
        <p role="status" className="mb-5 flex flex-wrap items-center gap-3 rounded-[20px] border border-berry/40 bg-berry/5 px-5 py-3 text-sm">
          <strong className="text-berry">
            {data.low_stock_count} item{data.low_stock_count === 1 ? ' is' : 's are'} at or below the low-stock level.
          </strong>
          {!filters.low_stock && (
            <button type="button" className="textlink" onClick={() => setFilter('low_stock', true)}>
              Show only those
            </button>
          )}
        </p>
      )}

      {adding && (
        <AddItemForm
          onCancel={() => setAdding(false)}
          onCreated={async (item) => {
            setAdding(false)
            await changed()
            open(item.id)
          }}
        />
      )}

      <div ref={detailRef} className="scroll-mt-4">
        {selected && (
          <ItemDetail
            key={selected}
            itemId={selected}
            canManage={canManage}
            canAdjust={canAdjust}
            historyKey={historyKey}
            onClose={() => setSelected(null)}
            onChanged={changed}
          />
        )}
      </div>

      <div className="mb-5 grid gap-3 rounded-[20px] bg-sage p-4 sm:grid-cols-2 lg:grid-cols-[2fr_1.3fr_1fr_auto] lg:items-end">
        <label>
          <span className="field-label">Search</span>
          <input className="field !py-2" type="search" placeholder="Item name" maxLength={120} value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <label>
          <span className="field-label">Category</span>
          <select className="field !py-2" value={filters.category} onChange={(e) => setFilter('category', e.target.value)}>
            <option value="">All categories</option>
            {CATEGORIES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Show</span>
          <select className="field !py-2" value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="active">In use</option>
            <option value="archived">Archived</option>
            <option value="all">All</option>
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm font-semibold">
          <input type="checkbox" className="h-4 w-4 accent-forest" checked={filters.low_stock} onChange={(e) => setFilter('low_stock', e.target.checked)} />
          Low stock only
        </label>
      </div>

      {error && (
        <div role="alert" className="mb-5 rounded-lg border border-berry/40 bg-berry/5 p-3 text-sm font-medium text-berry">
          {error}{' '}
          <button type="button" className="textlink ml-2" onClick={load}>
            Try again
          </button>
        </div>
      )}
      {!data && loading && <p role="status">Loading inventory…</p>}
      {data && data.items.length === 0 && (
        <div className="rounded-[20px] bg-white/60 p-8 text-sm">
          {filtered ? (
            <p>No items match these filters.</p>
          ) : (
            <p>
              No inventory items yet.{' '}
              {canManage ? 'Use “Add item” to record the first one, with the stock you have now.' : 'Someone with permission to manage items can add them.'}
            </p>
          )}
        </div>
      )}
      {data && data.items.length > 0 && (
        <div aria-busy={loading} className={loading ? 'opacity-60 transition-opacity' : ''}>
          <ItemTable items={data.items} selected={selected} onOpen={open} />
          <ItemCards items={data.items} selected={selected} onOpen={open} />
          <Pager total={data.total} limit={PAGE} offset={offset} onChange={setOffset} noun="items" />
        </div>
      )}

      <div className="mt-12">
        <h2 className="mb-1 text-[28px] tracking-[-0.6px]">Stock history</h2>
        <p className="mb-4 text-sm opacity-75">Every stock change, newest first, for all items. Entries cannot be edited or deleted.</p>
        <History itemId={null} refreshKey={historyKey} />
      </div>
    </section>
  )
}

function ItemTable({ items, selected, onOpen }) {
  return (
    <div className="hidden overflow-hidden rounded-[20px] border border-line bg-white/60 md:block">
      <table className="w-full text-left text-sm">
        <thead className="bg-sage text-xs uppercase tracking-[1.2px]">
          <tr>
            <th scope="col" className="px-4 py-3">Item</th>
            <th scope="col" className="px-4 py-3">Category</th>
            <th scope="col" className="px-4 py-3 text-right">In stock</th>
            <th scope="col" className="px-4 py-3 text-right">Low at</th>
            <th scope="col" className="px-4 py-3">Updated</th>
            <th scope="col" className="px-4 py-3"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className={`border-t border-line ${item.id === selected ? 'bg-citrus/40' : ''} ${item.is_active ? '' : 'opacity-70'}`}>
              <td className="px-4 py-3">
                <span className="font-semibold">{item.name}</span> <LowBadge item={item} />
              </td>
              <td className="px-4 py-3">{CATEGORY_LABEL[item.category]}</td>
              <td className={`px-4 py-3 text-right font-semibold tabular-nums ${item.is_low ? 'text-berry' : ''}`}>{qty(item.quantity, item.unit)}</td>
              <td className="px-4 py-3 text-right tabular-nums opacity-80">{item.low_stock_threshold === null ? '—' : qty(item.low_stock_threshold, item.unit)}</td>
              <td className="px-4 py-3 opacity-80">{formatDateTime(item.updated_at)}</td>
              <td className="px-4 py-3 text-right">
                <button type="button" className="textlink" onClick={() => onOpen(item.id)} aria-label={`Open ${item.name}`}>
                  Open
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ItemCards({ items, selected, onOpen }) {
  return (
    <ul className="grid gap-3 md:hidden">
      {items.map((item) => (
        <li key={item.id}>
          <button
            type="button"
            onClick={() => onOpen(item.id)}
            className={`w-full rounded-[20px] border p-4 text-left ${item.id === selected ? 'border-forest bg-citrus/40' : 'border-line bg-white/60'} ${item.is_active ? '' : 'opacity-70'}`}
          >
            <span className="flex items-start justify-between gap-3">
              <span>
                <span className="block font-semibold">{item.name}</span>
                <span className="block text-xs opacity-70">{CATEGORY_LABEL[item.category]}</span>
              </span>
              <span className={`text-right text-lg font-semibold tabular-nums ${item.is_low ? 'text-berry' : ''}`}>{qty(item.quantity, item.unit)}</span>
            </span>
            <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs opacity-80">
              <LowBadge item={item} />
              <span>Low at {item.low_stock_threshold === null ? '—' : qty(item.low_stock_threshold, item.unit)}</span>
              <span>Updated {formatDateTime(item.updated_at)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function Pager({ total, limit, offset, onChange, noun }) {
  if (total <= limit) return null
  const last = Math.min(offset + limit, total)
  return (
    <nav aria-label={`More ${noun}`} className="mt-4 flex flex-wrap items-center gap-4 text-sm">
      <button type="button" className="pill !py-2" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <span>
        {offset + 1}–{last} of {total}
      </span>
      <button type="button" className="pill !py-2" disabled={last >= total} onClick={() => onChange(offset + limit)}>
        Next
      </button>
    </nav>
  )
}

function AddItemForm({ onCancel, onCreated }) {
  const { handleAuthError } = useSession()
  const [form, setForm] = useState({ name: '', category: 'fruit_veg', unit: 'kg', low_stock_threshold: '', opening_quantity: '' })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  // Same key for retries of the same details; a new one once anything changes.
  const idempotencyKey = useRef(newKey())

  const set = (name, value) => {
    idempotencyKey.current = newKey()
    setForm((f) => ({ ...f, [name]: value }))
  }

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    const local = {
      name: form.name.trim() ? '' : 'Enter a name.',
      low_stock_threshold: quantityProblem(form.low_stock_threshold, form.unit, { required: false }),
      opening_quantity: quantityProblem(form.opening_quantity, form.unit, { required: false }),
    }
    if (Object.values(local).some(Boolean)) {
      setErrors(local)
      return
    }
    setBusy(true)
    setErrors({})
    setMessage(null)
    try {
      const item = await api('/staff/inventory/items', {
        method: 'POST',
        body: {
          name: form.name.trim(),
          category: form.category,
          unit: form.unit,
          low_stock_threshold: form.low_stock_threshold.trim() || null,
          opening_quantity: form.opening_quantity.trim() || null,
          idempotency_key: idempotencyKey.current,
        },
      })
      idempotencyKey.current = newKey()
      await onCreated(item)
    } catch (err) {
      if (handleAuthError(err)) return
      if (isUncertain(err)) {
        setMessage({ ok: false, text: form.opening_quantity.trim() ? UNCERTAIN : `${UNCERTAIN.split('.')[0]}. Search the list for it before adding it again.` })
        return
      }
      if (Object.keys(err.fields || {}).length) setErrors(err.fields)
      setMessage({ ok: false, text: `Not added. ${err.status === 403 ? 'You no longer have permission to add items.' : err.message}` })
    } finally {
      setBusy(false)
    }
  }

  const unitShort = UNIT_SHORT[form.unit]
  return (
    <form onSubmit={submit} noValidate className="mb-8 rounded-[20px] border border-forest/30 bg-white/70 p-5" aria-labelledby="add-item-title">
      <h2 id="add-item-title" className="mb-4 text-[26px] tracking-[-0.6px]">
        Add an inventory item
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <label className="sm:col-span-2 lg:col-span-1">
          <span className="field-label">Name</span>
          <input className="field" maxLength={120} value={form.name} aria-invalid={Boolean(errors.name)} placeholder="e.g. Bananas" onChange={(e) => set('name', e.target.value)} />
          {errors.name && <span className="field-error block">{errors.name}</span>}
        </label>
        <label>
          <span className="field-label">Category</span>
          <select className="field" value={form.category} onChange={(e) => set('category', e.target.value)}>
            {CATEGORIES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Unit</span>
          <select className="field" value={form.unit} aria-describedby="unit-note" onChange={(e) => set('unit', e.target.value)}>
            {UNITS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <span id="unit-note" className="mt-1 block text-xs opacity-70">
            Fixed once stock is recorded.
          </span>
        </label>
        <label>
          <span className="field-label">Stock now ({unitShort})</span>
          <input className="field" inputMode="decimal" value={form.opening_quantity} aria-invalid={Boolean(errors.opening_quantity)} placeholder="Optional" onChange={(e) => set('opening_quantity', e.target.value)} />
          <span className="mt-1 block text-xs opacity-70">Recorded as “Opening stock” in the history.</span>
          {errors.opening_quantity && <span className="field-error block">{errors.opening_quantity}</span>}
        </label>
        <label>
          <span className="field-label">Low-stock level ({unitShort})</span>
          <input className="field" inputMode="decimal" value={form.low_stock_threshold} aria-invalid={Boolean(errors.low_stock_threshold)} placeholder="Optional" onChange={(e) => set('low_stock_threshold', e.target.value)} />
          <span className="mt-1 block text-xs opacity-70">Flagged when stock is at or below this.</span>
          {errors.low_stock_threshold && <span className="field-error block">{errors.low_stock_threshold}</span>}
        </label>
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-4">
        <button type="submit" className="pill pill-dark !py-2" disabled={busy}>
          {busy ? 'Adding…' : 'Add item'}
        </button>
        <button type="button" className="textlink" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
      <div className="mt-3">
        <Message message={message} />
      </div>
    </form>
  )
}

function ItemDetail({ itemId, canManage, canAdjust, historyKey, onClose, onChanged }) {
  const { handleAuthError } = useSession()
  const [item, setItem] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState(null)

  const load = useCallback(async () => {
    setError('')
    try {
      setItem(await api(`/staff/inventory/items/${itemId}`))
    } catch (err) {
      if (!handleAuthError(err)) setError(err.status === 404 ? 'That item no longer exists.' : err.message)
    }
  }, [itemId, handleAuthError])

  useEffect(() => {
    load()
  }, [load])

  // After any change (or a refused one) show the item as the server has it now.
  const refresh = useCallback(
    async (next) => {
      if (next) setItem(next)
      else await load()
      await onChanged()
    },
    [load, onChanged],
  )

  if (!item) {
    return (
      <div className="mb-8 rounded-[20px] border border-line bg-white/60 p-5">
        <p role={error ? 'alert' : 'status'} className={error ? 'font-medium text-berry' : ''}>
          {error || 'Loading item…'}
        </p>
        {error && (
          <button type="button" className="textlink mt-3" onClick={onClose}>
            Close
          </button>
        )}
      </div>
    )
  }

  return (
    <article aria-labelledby="item-title" className="mb-8 rounded-[20px] border border-forest/40 bg-white/80 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[1.5px] opacity-70">{CATEGORY_LABEL[item.category]}</p>
          <h2 id="item-title" className="text-[30px] leading-tight tracking-[-0.8px]">
            {item.name}
          </h2>
        </div>
        <button type="button" className="textlink" onClick={onClose}>
          Close
        </button>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <div className="rounded-[16px] bg-sage p-3">
          <dt className="text-xs uppercase tracking-[1.2px] opacity-70">In stock</dt>
          <dd className={`text-2xl font-semibold tabular-nums ${item.is_low ? 'text-berry' : ''}`}>{qty(item.quantity, item.unit)}</dd>
        </div>
        <div className="rounded-[16px] bg-sage p-3">
          <dt className="text-xs uppercase tracking-[1.2px] opacity-70">Low at</dt>
          <dd className="text-2xl font-semibold tabular-nums">{item.low_stock_threshold === null ? '—' : qty(item.low_stock_threshold, item.unit)}</dd>
        </div>
        <div className="rounded-[16px] bg-sage p-3">
          <dt className="text-xs uppercase tracking-[1.2px] opacity-70">State</dt>
          <dd className="mt-1">
            {item.is_active ? (item.is_low ? <LowBadge item={item} /> : 'In use') : <LowBadge item={item} />}
          </dd>
        </div>
        <div className="rounded-[16px] bg-sage p-3">
          <dt className="text-xs uppercase tracking-[1.2px] opacity-70">Updated</dt>
          <dd className="mt-1">{formatDateTime(item.updated_at)}</dd>
        </div>
      </dl>
      {notice && (
        <p role="status" className="mt-4 rounded-lg border border-amber bg-citrus/50 p-3 text-sm">
          {notice}
        </p>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        {canAdjust && item.is_active && (
          <StockForm
            key={item.version}
            item={item}
            onDone={async (result) => {
              const m = result.movement
              setNotice(`Recorded: ${KIND_LABEL[m.kind]} ${signed(m.quantity_change)} ${UNIT_SHORT[m.unit]}. Now ${qty(m.balance_after, m.unit)}.`)
              await refresh(result.item)
            }}
            onStale={async (text) => {
              setNotice(text)
              await refresh()
            }}
          />
        )}
        {canAdjust && !item.is_active && (
          <p className="rounded-[20px] bg-sage p-5 text-sm">This item is archived. Restore it to record stock.</p>
        )}
        {canManage && (
          <EditForm
            key={`edit-${item.version}`}
            item={item}
            onSaved={async (next, text) => {
              setNotice(text)
              await refresh(next)
            }}
            onStale={async (text) => {
              setNotice(text)
              await refresh()
            }}
          />
        )}
      </div>

      <h3 className="mb-3 mt-8 text-[22px] tracking-[-0.4px]">History of this item</h3>
      <History itemId={item.id} refreshKey={`${historyKey}-${item.version}`} />
    </article>
  )
}

const STOCK_MODES = [
  ['stock_in', 'Stock in', 'Amount received'],
  ['stock_out', 'Stock out', 'Amount used or thrown away'],
  ['adjustment', 'Correction', 'Quantity counted now'],
]

function StockForm({ item, onDone, onStale }) {
  const { handleAuthError } = useSession()
  const [kind, setKind] = useState('stock_in')
  const [quantity, setQuantity] = useState('')
  const [reason, setReason] = useState('')
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const idempotencyKey = useRef(newKey())
  const change = (setter) => (value) => {
    idempotencyKey.current = newKey()
    setter(value)
  }

  const isCount = kind === 'adjustment'
  const problem = quantityProblem(quantity, item.unit, { allowZero: isCount })
  let preview = ''
  if (!problem) {
    const current = Number(item.quantity)
    const amount = Number(quantity)
    const after = kind === 'stock_in' ? current + amount : kind === 'stock_out' ? current - amount : amount
    preview = after < 0 ? `Only ${qty(item.quantity, item.unit)} in stock.` : `Stock after: ${qty(String(Math.round(after * 1000) / 1000), item.unit)}`
  }

  const submit = async (event) => {
    event.preventDefault()
    if (busy) return
    const local = { quantity: problem, reason: isCount && !reason.trim() ? 'Say why, for example “Weekly count”.' : '' }
    if (Object.values(local).some(Boolean)) {
      setErrors(local)
      return
    }
    setBusy(true)
    setErrors({})
    setMessage(null)
    try {
      const result = await api(`/staff/inventory/items/${item.id}/movements`, {
        method: 'POST',
        body: {
          kind,
          quantity: quantity.trim(),
          reason: reason.trim() || null,
          ...(isCount ? { version: item.version } : {}),
          idempotency_key: idempotencyKey.current,
        },
      })
      idempotencyKey.current = newKey()
      await onDone(result)
    } catch (err) {
      if (handleAuthError(err)) return
      if (err.code === 'stale_update') {
        await onStale('The stock changed while you were counting. It has been reloaded; please count again.')
        return
      }
      if (isUncertain(err)) {
        setMessage({ ok: false, text: UNCERTAIN })
        return
      }
      if (Object.keys(err.fields || {}).length) setErrors(err.fields)
      setMessage({ ok: false, text: `Not recorded. ${err.status === 403 ? 'You no longer have permission to change stock.' : err.fields?.quantity || err.message}` })
    } finally {
      setBusy(false)
    }
  }

  const [, , quantityLabel] = STOCK_MODES.find(([value]) => value === kind)
  return (
    <form onSubmit={submit} noValidate className="rounded-[20px] bg-sage p-5" aria-labelledby={`stock-title-${item.id}`}>
      <h3 id={`stock-title-${item.id}`} className="mb-3 text-[22px] tracking-[-0.4px]">
        Record stock
      </h3>
      <div role="group" aria-label="Kind of change" className="mb-4 flex flex-wrap gap-2">
        {STOCK_MODES.map(([value, label]) => (
          <button key={value} type="button" className="chip" aria-pressed={kind === value} onClick={() => change(setKind)(value)}>
            {label}
          </button>
        ))}
      </div>
      <label className="block">
        <span className="field-label">
          {quantityLabel} ({UNIT_SHORT[item.unit]})
        </span>
        <input className="field" inputMode={item.unit === 'piece' ? 'numeric' : 'decimal'} autoComplete="off" value={quantity} aria-invalid={Boolean(errors.quantity)} onChange={(e) => change(setQuantity)(e.target.value)} />
        {errors.quantity && <span className="field-error block">{errors.quantity}</span>}
      </label>
      {isCount && <p className="mt-2 text-xs opacity-75">Enter what is actually on the shelf. The difference is recorded as a correction.</p>}
      <p className="mt-2 min-h-5 text-sm tabular-nums">{quantity && preview}</p>
      <label className="mt-2 block">
        <span className="field-label">Reason {isCount ? '(required)' : '(optional)'}</span>
        <input className="field" maxLength={300} value={reason} aria-invalid={Boolean(errors.reason)} placeholder={isCount ? 'e.g. Weekly count, spoiled' : 'e.g. Market delivery'} onChange={(e) => change(setReason)(e.target.value)} />
        {errors.reason && <span className="field-error block">{errors.reason}</span>}
      </label>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="submit" className="pill pill-dark !py-2" disabled={busy}>
          {busy ? 'Recording…' : isCount ? 'Record correction' : kind === 'stock_in' ? 'Record stock in' : 'Record stock out'}
        </button>
      </div>
      <div className="mt-3">
        <Message message={message} />
      </div>
    </form>
  )
}

function EditForm({ item, onSaved, onStale }) {
  const { handleAuthError } = useSession()
  const [form, setForm] = useState({
    name: item.name,
    category: item.category,
    unit: item.unit,
    low_stock_threshold: item.low_stock_threshold ?? '',
  })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (name, value) => setForm((f) => ({ ...f, [name]: value }))
  const dirty =
    form.name !== item.name || form.category !== item.category || form.unit !== item.unit || form.low_stock_threshold !== (item.low_stock_threshold ?? '')

  const send = async (body, okText) => {
    if (busy) return
    setBusy(true)
    setErrors({})
    setMessage(null)
    try {
      const next = await api(`/staff/inventory/items/${item.id}`, { method: 'PATCH', body: { version: item.version, ...body } })
      await onSaved(next, okText) // the form is replaced by one showing the saved values
    } catch (err) {
      if (handleAuthError(err)) return
      if (err.code === 'stale_update') {
        await onStale('Someone else changed this item a moment ago. It has been reloaded; please check and try again.')
        return
      }
      if (Object.keys(err.fields || {}).length) setErrors(err.fields)
      setMessage({ ok: false, text: `Not saved. ${err.status === 403 ? 'You no longer have permission to edit items.' : Object.values(err.fields || {})[0] || err.message}` })
    } finally {
      setBusy(false)
    }
  }

  const save = (event) => {
    event.preventDefault()
    const local = {
      name: form.name.trim() ? '' : 'Enter a name.',
      low_stock_threshold: quantityProblem(String(form.low_stock_threshold), form.unit, { required: false }),
    }
    if (Object.values(local).some(Boolean)) {
      setErrors(local)
      return
    }
    send(
      {
        name: form.name.trim(),
        category: form.category,
        ...(form.unit !== item.unit ? { unit: form.unit } : {}),
        low_stock_threshold: String(form.low_stock_threshold).trim() || null,
      },
      'Details saved. Stock was not changed.',
    )
  }

  return (
    <form onSubmit={save} noValidate className="rounded-[20px] border border-line p-5" aria-labelledby={`edit-title-${item.id}`}>
      <h3 id={`edit-title-${item.id}`} className="mb-3 text-[22px] tracking-[-0.4px]">
        Item details
      </h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="sm:col-span-2">
          <span className="field-label">Name</span>
          <input className="field" maxLength={120} value={form.name} aria-invalid={Boolean(errors.name)} onChange={(e) => set('name', e.target.value)} />
          {errors.name && <span className="field-error block">{errors.name}</span>}
        </label>
        <label>
          <span className="field-label">Category</span>
          <select className="field" value={form.category} onChange={(e) => set('category', e.target.value)}>
            {CATEGORIES.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="field-label">Unit</span>
          <select className="field" value={form.unit} disabled={item.has_movements} aria-invalid={Boolean(errors.unit)} onChange={(e) => set('unit', e.target.value)}>
            {UNITS.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {item.has_movements && <span className="mt-1 block text-xs opacity-70">Fixed: stock has been recorded.</span>}
          {errors.unit && <span className="field-error block">{errors.unit}</span>}
        </label>
        <label className="sm:col-span-2">
          <span className="field-label">Low-stock level ({UNIT_SHORT[form.unit]})</span>
          <input className="field" inputMode="decimal" value={form.low_stock_threshold} placeholder="None" aria-invalid={Boolean(errors.low_stock_threshold)} onChange={(e) => set('low_stock_threshold', e.target.value)} />
          {errors.low_stock_threshold && <span className="field-error block">{errors.low_stock_threshold}</span>}
        </label>
      </div>
      <p className="mt-3 text-xs opacity-75">Editing details never changes the stock. Use “Record stock” for that.</p>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <button type="submit" className="pill !py-2" disabled={busy || !dirty}>
          {busy ? 'Saving…' : 'Save details'}
        </button>
        {item.is_active ? (
          <button
            type="button"
            className="textlink"
            disabled={busy}
            onClick={() =>
              window.confirm(`Archive ${item.name}? It leaves the list and no stock can be recorded, but its history is kept. You can restore it later.`) &&
              send({ is_active: false }, 'Archived. Its history is kept.')
            }
          >
            Archive item
          </button>
        ) : (
          <button type="button" className="textlink" disabled={busy} onClick={() => send({ is_active: true }, 'Restored.')}>
            Restore item
          </button>
        )}
      </div>
      <div className="mt-3">
        <Message message={message} />
      </div>
    </form>
  )
}

function History({ itemId, refreshKey }) {
  const { handleAuthError } = useSession()
  const [offset, setOffset] = useState(0)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const params = new URLSearchParams([['limit', HISTORY_PAGE], ['offset', offset], ...(itemId ? [['item_id', itemId]] : [])])
    try {
      setData(await api(`/staff/inventory/movements?${params}`))
    } catch (err) {
      if (!handleAuthError(err)) setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [itemId, offset, handleAuthError])

  useEffect(() => {
    load()
  }, [load, refreshKey])

  if (error) {
    return (
      <p role="alert" className="text-sm font-medium text-berry">
        Could not load the history. {error}{' '}
        <button type="button" className="textlink ml-2" onClick={load}>
          Try again
        </button>
      </p>
    )
  }
  if (!data) return <p role="status">{loading ? 'Loading history…' : ''}</p>
  if (data.total === 0) return <p className="rounded-[20px] bg-white/60 p-5 text-sm">No stock has been recorded yet.</p>

  return (
    <div aria-busy={loading}>
      <div className="hidden overflow-hidden rounded-[20px] border border-line bg-white/60 md:block">
        <table className="w-full text-left text-sm">
          <thead className="bg-sage text-xs uppercase tracking-[1.2px]">
            <tr>
              <th scope="col" className="px-4 py-3">When</th>
              {!itemId && <th scope="col" className="px-4 py-3">Item</th>}
              <th scope="col" className="px-4 py-3">Change</th>
              <th scope="col" className="px-4 py-3 text-right">Quantity</th>
              <th scope="col" className="px-4 py-3 text-right">Balance after</th>
              <th scope="col" className="px-4 py-3">By</th>
              <th scope="col" className="px-4 py-3">Reason</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((m) => (
              <tr key={m.id} className="border-t border-line align-top">
                <td className="whitespace-nowrap px-4 py-3">{formatDateTime(m.created_at)}</td>
                {!itemId && <td className="px-4 py-3 font-semibold">{m.item_name}</td>}
                <td className="px-4 py-3">{KIND_LABEL[m.kind]}</td>
                <td className={`px-4 py-3 text-right font-semibold tabular-nums ${m.quantity_change.startsWith('-') ? 'text-berry' : ''}`}>{signed(m.quantity_change)} {UNIT_SHORT[m.unit]}</td>
                <td className="px-4 py-3 text-right tabular-nums">{qty(m.balance_after, m.unit)}</td>
                <td className="px-4 py-3">
                  {m.actor_name} <span className="text-xs opacity-60">({m.actor_role})</span>
                </td>
                <td className="px-4 py-3 opacity-85">{m.reason || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="grid gap-2 md:hidden">
        {data.items.map((m) => (
          <li key={m.id} className="rounded-[16px] border border-line bg-white/60 p-3 text-sm">
            <div className="flex items-start justify-between gap-3">
              <span>
                <span className="block font-semibold">{itemId ? KIND_LABEL[m.kind] : m.item_name}</span>
                {!itemId && <span className="block text-xs opacity-70">{KIND_LABEL[m.kind]}</span>}
              </span>
              <span className={`text-right font-semibold tabular-nums ${m.quantity_change.startsWith('-') ? 'text-berry' : ''}`}>
                {signed(m.quantity_change)} {UNIT_SHORT[m.unit]}
                <span className="block text-xs font-normal opacity-75">now {qty(m.balance_after, m.unit)}</span>
              </span>
            </div>
            <p className="mt-1 text-xs opacity-75">
              {formatDateTime(m.created_at)} · {m.actor_name} ({m.actor_role})
            </p>
            {m.reason && <p className="mt-1 text-xs">“{m.reason}”</p>}
          </li>
        ))}
      </ul>
      <Pager total={data.total} limit={HISTORY_PAGE} offset={offset} onChange={setOffset} noun="history" />
    </div>
  )
}

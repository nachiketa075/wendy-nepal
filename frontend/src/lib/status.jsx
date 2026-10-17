export const STATUS_LABEL = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  declined: 'Declined',
  cancelled: 'Cancelled',
  checked_in: 'Checked in',
  completed: 'Completed',
  no_show: 'No-show',
}

const STATUS_STYLE = {
  pending: 'bg-citrus text-forest',
  confirmed: 'bg-forest text-cream',
  declined: 'bg-berry/10 text-berry',
  cancelled: 'bg-line text-forest',
  checked_in: 'bg-forest/15 text-forest',
  completed: 'bg-sage text-forest border border-forest/30',
  no_show: 'bg-berry/10 text-berry',
}

export const StatusBadge = ({ status }) => (
  <span className={`whitespace-nowrap rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[1.5px] ${STATUS_STYLE[status] || 'bg-line'}`}>
    {STATUS_LABEL[status] || status}
  </span>
)

/** Re-runs `callback` every `ms` while the tab is visible, and when it becomes visible again. */
export function startPolling(callback, ms) {
  const tick = () => document.visibilityState === 'visible' && callback()
  const timer = setInterval(tick, ms)
  document.addEventListener('visibilitychange', tick)
  return () => {
    clearInterval(timer)
    document.removeEventListener('visibilitychange', tick)
  }
}

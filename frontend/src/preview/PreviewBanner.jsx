export default function PreviewBanner({ children }) {
  return (
    <div role="note" className="border-b border-amber bg-citrus px-[6%] py-3 text-sm leading-[1.6]">
      <strong>Development preview · fictional data.</strong> {children || 'Nothing on this screen is saved or sent to the server, and no real booking is shown.'}
    </div>
  )
}

export const PreviewTag = () => (
  <span className="ml-2 rounded-full border border-amber bg-citrus/60 px-2 py-0.5 align-middle font-sans text-[10px] font-bold uppercase tracking-[1.5px]">
    Preview only
  </span>
)

export const STATUS_STYLE = {
  pending: 'bg-citrus text-forest',
  confirmed: 'bg-forest text-cream',
  declined: 'bg-berry/10 text-berry',
  cancelled: 'bg-line text-forest',
  checked_in: 'bg-forest/15 text-forest',
}
export const STATUS_LABEL = { pending: 'Pending', confirmed: 'Confirmed', declined: 'Declined', cancelled: 'Cancelled', checked_in: 'Checked in' }

export const StatusBadge = ({ status }) => (
  <span className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-[1.5px] ${STATUS_STYLE[status]}`}>{STATUS_LABEL[status]}</span>
)

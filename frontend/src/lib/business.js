// Shared business details. Phone and WhatsApp were confirmed by the owner.
// Opening hours, ratings and founding history stay out until they are confirmed too.
export const BUSINESS = {
  name: 'Wendy Juice Shop',
  addressLines: ['Pahari Marga / 15th Street', 'Lakeside, Pokhara 33700, Nepal'],
  phoneDisplay: '+977 985-6031094',
  phoneHref: 'tel:+9779856031094',
  // Opens a WhatsApp chat. It does not send or confirm a booking.
  whatsappUrl: 'https://wa.me/9779856031094',
  email: 'kushwaha_3@hotmail.com',
  mapsUrl: 'https://www.google.com/maps/search/?api=1&query=Wendy+Juice+Shop+Pokhara',
  facebookUrl: 'https://www.facebook.com/wendyjuiceshop/',
}

// How menu prices are written. The printed menu uses "Rs."; change it here only.
export const CURRENCY = { prefix: 'Rs.', locale: 'en-IN' }

export function formatPrice(value) {
  if (value === null || value === undefined || value === '') return ''
  return `${CURRENCY.prefix} ${Number(value).toLocaleString(CURRENCY.locale, { maximumFractionDigits: 2 })}`
}

export const MENU_PDF_URL = '/menu/wendy-juice-shop-menu.pdf'
export const LOGO_URL = '/images/wendy-juice-shop-logo.webp'

export const SOURCES = {
  google: BUSINESS.mapsUrl,
  tripadvisor:
    'https://www.tripadvisor.com/Restaurant_Review-g293891-d10452354-Reviews-Wendy_Juice_Shop-Pokhara_Gandaki_Zone_Western_Region.html',
  happycow: 'https://www.happycow.net/reviews/wendy-juice-shop-nepal-153127',
  facebook: BUSINESS.facebookUrl,
}

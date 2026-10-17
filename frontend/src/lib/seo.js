// Search-engine metadata for the public pages. Used in two places:
//  * at build time (vite.config.js) to write each page's own HTML file, so the
//    title, description and canonical address are in the HTML the server sends;
//  * in the browser (setPageMeta) to keep them right when moving between pages.
// The homepage values must match index.html; the build checks this.
// Plain JavaScript (no JSX) so vite.config.js can import it.

export const SITE_URL = 'https://wendyjuiceshop.com'

export const PAGES = {
  '/': {
    title: 'Wendy Juice Shop Pokhara | Fresh Juices & Smoothies',
    description:
      'Wendy Juice Shop in Lakeside, Pokhara, Nepal: fresh juices, smoothies, smoothie bowls and breakfast. See the menu and request a table online.',
  },
  '/menu': {
    title: 'Menu | Wendy Juice Shop Pokhara',
    description:
      'The full Wendy Juice Shop menu: fresh juices, smoothies, smoothie bowls, breakfast and more, with prices. Lakeside, Pokhara, Nepal.',
  },
}

/** Set the title, description, canonical and social tags for a public page. */
export function setPageMeta(path) {
  const page = PAGES[path]
  if (!page || typeof document === 'undefined') return
  const url = `${SITE_URL}${path === '/' ? '/' : path}`
  document.title = page.title
  const set = (selector, attr, value) => document.querySelector(selector)?.setAttribute(attr, value)
  set('meta[name="description"]', 'content', page.description)
  set('link[rel="canonical"]', 'href', url)
  set('meta[property="og:url"]', 'content', url)
  set('meta[property="og:title"]', 'content', page.title)
  set('meta[property="og:description"]', 'content', page.description)
  set('meta[name="twitter:title"]', 'content', page.title)
  set('meta[name="twitter:description"]', 'content', page.description)
}

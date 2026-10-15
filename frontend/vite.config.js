import fs from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { PAGES, SITE_URL } from './src/lib/seo.js'

// The API is reached through this proxy so the browser sees one origin and the
// owner session cookie stays same-site in development.
const apiTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

const escapeAttr = (text) => text.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')

/**
 * Writes dist/<page>.html for each public page other than the homepage: a copy
 * of the built index.html with that page's title, description, canonical and
 * social tags, so search engines get them without running JavaScript. The
 * server sends /menu from menu.html (frontend/Caddyfile, try_files).
 */
function publicPageHeads() {
  let outDir
  return {
    name: 'wendy-public-page-heads',
    apply: 'build',
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir)
    },
    closeBundle() {
      const index = fs.readFileSync(path.join(outDir, 'index.html'), 'utf8')
      if (!index.includes(`<title>${escapeAttr(PAGES['/'].title)}</title>`)) {
        throw new Error("index.html <title> does not match PAGES['/'] in src/lib/seo.js")
      }
      for (const [route, page] of Object.entries(PAGES)) {
        if (route === '/') continue
        const url = `${SITE_URL}${route}`
        const title = escapeAttr(page.title)
        const description = escapeAttr(page.description)
        const replacements = [
          [/<title>[^<]*<\/title>/, `<title>${title}</title>`],
          [/(<meta name="description" content=")[^"]*/, `$1${description}`],
          [/(<link rel="canonical" href=")[^"]*/, `$1${url}`],
          [/(<meta property="og:url" content=")[^"]*/, `$1${url}`],
          [/(<meta property="og:title" content=")[^"]*/, `$1${title}`],
          [/(<meta property="og:description" content=")[^"]*/, `$1${description}`],
          [/(<meta name="twitter:title" content=")[^"]*/, `$1${title}`],
          [/(<meta name="twitter:description" content=")[^"]*/, `$1${description}`],
        ]
        let html = index
        for (const [pattern, value] of replacements) {
          if (!pattern.test(html)) throw new Error(`index.html is missing ${pattern} needed for ${route}`)
          html = html.replace(pattern, value)
        }
        fs.writeFileSync(path.join(outDir, `${route.slice(1)}.html`), html)
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), publicPageHeads()],
  server: {
    host: true,
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: false, xfwd: true } },
  },
})

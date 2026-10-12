// Development-only UI preview switch.
//
// The customer and employee screens have no backend yet. To review their design,
// run the Vite dev server with VITE_ENABLE_PREVIEW=true. Both conditions must
// hold, so a production build (where import.meta.env.DEV is false) can never
// enable it, whatever the environment says. Preview screens use fictional data
// from src/preview/fixtures.js, keep everything in memory, and call no API.
export const PREVIEW_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_PREVIEW === 'true'

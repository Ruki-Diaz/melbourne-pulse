# Melbourne Pulse: web

Next.js 16 (App Router) site. Server components read Neon through the read-only
`web_reader` role (`DATABASE_URL_READONLY`, server-only). Pages render on
request (`dynamic = "force-dynamic"`) and Vercel's CDN caches them for an hour
(`Vercel-CDN-Cache-Control`, see `next.config.ts`). No ISR, so no ISR writes.

```bash
cp .env.example .env.local   # fill in values
npm install
npm run dev
```

See the [root README](../README.md) for architecture and setup.

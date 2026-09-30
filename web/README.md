# Melbourne Pulse: web

Next.js 16 (App Router) site. Server components read Neon through the read-only
`web_reader` role (`DATABASE_URL_READONLY`, server-only). Pages use
`revalidate = 3600`, and `POST /api/revalidate` (Bearer `REVALIDATE_SECRET`)
refreshes them right after each hourly ingest.

```bash
cp .env.example .env.local   # fill in values
npm install
npm run dev
```

See the [root README](../README.md) for architecture and setup.

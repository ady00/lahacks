# photon/ — manager approval by text

A Node sidecar that texts the manager (iMessage via Photon Spectrum) when a case waits for
pre-approval and posts their YES/NO back to the API. No API or dashboard changes.

```
pnpm install
MANAGER_PHONE=+1310xxxxxxx SPECTRUM_PROJECT_ID=... SPECTRUM_PROJECT_SECRET=... API_URL=http://localhost:8000 pnpm start
pnpm test
```

Credentials: https://app.photon.codes → project → Settings. Free plan texts from a shared-pool
number, so the manager's phone sees the first text as an unknown sender — have them reply from it.

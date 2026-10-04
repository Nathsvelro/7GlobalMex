# Deploy the phone app to Vercel

Vercel hosts only the **phone app** (`app/` + `content/`). That is all a farmer's phone needs: Vercel serves it over
HTTPS, so the service worker can store the app, the model, the cards and the audio, and the app then works in airplane
mode on any phone, iPhone included. The **co-op hub** stays on the co-op computer (`./run.sh`); see "Why not the hub"
below.

The repository already contains the configuration:

| File | What it does |
|---|---|
| `vercel.json` | Build: runs `scripts/vercel_build.sh`. Serves `public/`. Redirects `/` to `/app/`. Adds trailing slashes so `/app` becomes `/app/` (relative paths need it). `app/sw.js` is never cached, so phones see new versions. Sends `/api/*` to the public DEMO hub on Render, `https://cafetal-hub-demo.onrender.com` ([DEPLOY_HUB_RENDER.md](DEPLOY_HUB_RENDER.md)); two rules, with and without the trailing slash Vercel adds. |
| `scripts/vercel_build.sh` | Copies `app/` and `content/` into `public/` (they must stay side by side: the app loads `../content/cards.json`). Only these two folders are served. It prints the folder it runs in, and stops with a plain message if `app/` and `content/` are not there. |

## Steps in the Vercel dashboard

1. **Add New… → Project → Import** the GitHub repository `Nathsvelro/7GlobalMex`.
2. **Root Directory:** leave it empty (the repository root). Not `app`: the app needs `content/` next to it.
3. **Framework Preset:** Other. Leave Build Command, Output Directory and Install Command empty, with their override
   switches off: `vercel.json` sets them.
4. **Deploy.**
5. Open `https://<your-project>.vercel.app/` (it redirects to `/app/`). Wait for **"Ready to use without internet"**,
   then try airplane mode.

If the build log says `ERROR: app/ and content/ are not in this folder`, the Root Directory is wrong (step 2). Change it,
then **Redeploy** the newest deployment.

The production URL is built from the **production branch** (`main` by default). Preview URLs for other branches can be
protected by Vercel Authentication (Settings → Deployment Protection), so share the production URL with judges.

## Before you share the link

- **SMS number.** "Send by SMS" opens the phone's SMS app addressed to `gateway_number` in `app/config.json`
  (now a DEMO number, `+254700000000`). On a public link people may really send it: set the co-op's number or a team
  phone, or set it to `""` so the SMS app opens with no recipient. Then run `python3 scripts/bump_sw_version.py` and
  commit `app/sw.js` too.
- **Every app or content change:** run `python3 scripts/bump_sw_version.py` before you push (`./run.sh` does it for
  you), otherwise phones keep the cached copy.
- **DEMO sample photos.** With `"demo_samples": true` in `app/config.json` (this build), the Home screen shows seven
  sample leaf photos, so judges and the video can try the app without a coffee leaf. Each one is checked by the real
  model on the phone, and its result says "DEMO: sample data" with the photo's credit. For a real co-op, set it to
  `false`, then run `python3 scripts/bump_sw_version.py` and commit `app/sw.js` too.
- **iPhone:** use "Add to Home Screen". Safari can clear a website's offline storage after about 7 days without use.
- **Hub buttons.** "Send (SIMULATED)" and "Send photos to the co-op (Wi-Fi)" appear only when a co-op hub answers. On the
  Vercel copy, `/api/*` goes to the public DEMO hub on Render, so they appear once that hub is awake: it sleeps after 15
  minutes without visits and takes up to a minute to wake (the app pings it when it opens). Check after a deploy:
  `https://<your-project>.vercel.app/api/health` should answer `{"ok":true, … "public_demo":true}`. To cut the Vercel
  copy off from the hub, delete `rewrites` from `vercel.json`.
- **Licences.** The model was trained partly on non-commercial data (iNaturalist CC BY-NC photos, Imagenette). Keep
  the deployment non-commercial (Vercel's Hobby plan requires that too) and keep the credits in `README.md`.
- **Privacy.** Diagnosis runs on the phone and records stay on it until someone taps "Send (SIMULATED)" or "Send photos
  to the co-op (Wi-Fi)". Those taps send the record (and, for the second, its photo) through Vercel to the public DEMO
  hub on Render, where anyone with the hub link can see it until the hub restarts. Vercel stores nothing.

Tested here (not on Vercel itself): the `buildCommand` output served from a static server on localhost: the app
installed its offline cache, then with every request blocked it showed the three languages, diagnosed
`model/demo_samples/roya_1.jpg` as rust with code `CAF1 M0123 RUST 99 …`, and played the English audio from the cache.

## Why not the hub

The hub is FastAPI + SQLite with photo uploads and a content page that edits `content/cards.json`. Vercel runs Python
as short-lived functions with no lasting disk, so the database, photos and card edits would be lost. It also has no
login yet, and its consent text promises that member data stays on the co-op computer.

For an online hub demo, a public DEMO-only copy now exists for Render: [DEPLOY_HUB_RENDER.md](DEPLOY_HUB_RENDER.md).
It holds only fake DEMO data, reloads it on every start (so nothing needs to last), and has content edits off. The
Vercel copy of the app reaches it through the `/api/*` rewrite above. A real co-op still runs the hub on its own computer.

# Deploy the phone app to Vercel

Vercel hosts only the **phone app** (`app/` + `content/`). That is all a farmer's phone needs: Vercel serves it over
HTTPS, so the service worker can store the app, the model, the cards and the audio, and the app then works in airplane
mode on any phone, iPhone included. The **co-op hub** stays on the co-op computer (`./run.sh`); see "Why not the hub"
below.

The repository already contains the configuration:

| File | What it does |
|---|---|
| `vercel.json` | Build: copy `app/` and `content/` into `public/` (they must stay side by side: the app loads `../content/cards.json`). Serves `public/`. Redirects `/` to `/app/`. Adds trailing slashes so `/app` becomes `/app/` (relative paths need it). `app/sw.js` is never cached, so phones see new versions. |
| `.vercelignore` | Uploads only `app/`, `content/` and `vercel.json` (not the hub, model training, reports or tests). |

## Steps in the Vercel dashboard

1. **Add New… → Project → Import** the GitHub repository `Nathsvelro/7GlobalMex`.
2. **Framework Preset:** Other. Leave Build Command, Output Directory and Install Command empty: `vercel.json` sets them.
3. **Deploy.**
4. Open `https://<your-project>.vercel.app/` (it redirects to `/app/`). Wait for **"Ready to use without internet"**,
   then try airplane mode.

The production URL is built from the **production branch** (`main` by default). Preview URLs for other branches can be
protected by Vercel Authentication (Settings → Deployment Protection), so share the production URL with judges.

## Before you share the link

- **SMS number.** "Send by SMS" opens the phone's SMS app addressed to `gateway_number` in `app/config.json`
  (now a DEMO number, `+254700000000`). On a public link people may really send it: set the co-op's number or a team
  phone, or set it to `""` so the SMS app opens with no recipient. Then run `python3 scripts/bump_sw_version.py` and
  commit `app/sw.js` too.
- **Every app or content change:** run `python3 scripts/bump_sw_version.py` before you push (`./run.sh` does it for
  you), otherwise phones keep the cached copy.
- **iPhone:** use "Add to Home Screen". Safari can clear a website's offline storage after about 7 days without use.
- **No hub buttons.** "Send (SIMULATED)" and "Send photos to the co-op (Wi-Fi)" appear only when the co-op hub answers, so they are hidden
  on the Vercel copy. Diagnosis, audio, history and the SMS code work.
- **Licences.** The model was trained partly on non-commercial data (iNaturalist CC BY-NC photos, Imagenette). Keep
  the deployment non-commercial (Vercel's Hobby plan requires that too) and keep the credits in `README.md`.
- **Privacy.** No farmer data reaches Vercel: diagnosis runs on the phone and records stay on it. Vercel only logs the
  download of the app files.

Tested here (not on Vercel itself): the `buildCommand` output served from a static server on localhost: the app
installed its offline cache, then with every request blocked it showed the three languages, diagnosed
`model/demo_samples/roya_1.jpg` as rust with code `CAF1 M0123 RUST 99 …`, and played the English audio from the cache.

## Why not the hub

The hub is FastAPI + SQLite with photo uploads and a content page that edits `content/cards.json`. Vercel runs Python
as short-lived functions with no lasting disk, so the database, photos and card edits would be lost. It also has no
login yet, and its consent text promises that member data stays on the co-op computer. For an online hub demo, run a
separate DEMO-only copy behind a password on a host with a persistent disk (for example Render, Railway or Fly.io),
where `./run.sh` works almost unchanged.

# Deploy a public DEMO copy of the hub to Render

This puts a **public online DEMO copy** of the co-op hub on Render's free plan, so judges can open one HTTPS link:

- `<link>/` is the co-op hub.
- `<link>/app/` is the phone app. The hub serves it, so the hub buttons ("Send (SIMULATED)" and "Send photos to the
  co-op (Wi-Fi)") work here.

The hub has the made-up DEMO data and the SIMULATED SMS gateway: no real SMS is sent. The link is HTTPS, so the phone
app stores itself on the first load and then works offline.

This copy is only for judges and the video. A real co-op runs the hub on its own computer (`./run.sh`), where member
data stays.

The repository already contains the configuration:

| File | What it does |
|---|---|
| `render.yaml` | Render Blueprint: one free web service, `cafetal-hub-demo`, on Python 3.11.9. Build: `pip install -r requirements.txt`. Start: `sh scripts/render_start.sh`. Sets `CAFETAL_PUBLIC_DEMO=1`. |
| `scripts/render_start.sh` | Loads fresh DEMO data (`python -m hub.seed --reset`), then starts the hub on the port Render gives it. |

With `CAFETAL_PUBLIC_DEMO=1`, every hub page shows a "PUBLIC ONLINE DEMO" banner under the menu, and content edits are
off (see below).

## Steps in the Render dashboard

1. Sign in at https://dashboard.render.com with GitHub.
2. **New → Blueprint.**
3. Choose the repository `Nathsvelro/7GlobalMex` and the branch that has `render.yaml` (`main` once merged).
4. **Apply** (the button may say **Deploy Blueprint**). Render creates the service from `render.yaml`.
5. Wait until the service says **Live**. The first build takes a few minutes.
6. The link is at the top of the service page: `https://cafetal-hub-demo.onrender.com`, or that name with a suffix if
   it is taken.

## After the deploy

- Open `<link>/`: the hub, with the banner.
- Open `<link>/app/` on a phone or in Chrome. Wait for **"Ready to use without internet"**.

## Free plan

- The service sleeps after 15 minutes without visits. The next visit wakes it, which takes up to about a minute.
- Every start reloads fresh DEMO data, with dates counted from that day. Anything visitors changed is gone.
- So open the link about a minute before judging or recording.

## It is public

- Anyone with the link can see and change the DEMO data.
- Do not type real names or phone numbers.
- Photos sent with "Send photos to the co-op (Wi-Fi)" are visible to anyone with the link until the next restart.
- Content edits are off. On the Content page, marking a card verified (or not) and saving a recording answer 403
  (forbidden). To verify cards or upload recordings, run the hub on your own computer (`./run.sh`).

## Connecting the Vercel phone app

Ours is live at https://cafetal-hub-demo.onrender.com/. The Vercel copy of the phone app
([DEPLOY_VERCEL.md](DEPLOY_VERCEL.md)) reaches it through two rewrites in `vercel.json` that send `/api/*` to that link
(one for paths with the trailing slash Vercel adds, one without). So "Send (SIMULATED)" and "Send photos to the co-op
(Wi-Fi)" also work from the Vercel link, once the hub is awake. If the Render link changes, change it in both rules.

Check after a Vercel deploy: `https://<your-project>.vercel.app/api/health` should answer
`{"ok":true, … "public_demo":true}` (wait up to a minute if the hub was asleep).

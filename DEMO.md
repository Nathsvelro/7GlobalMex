# Cafetal demo, click by click

This is the whole journey for the 2–5 minute video and for judges trying Cafetal themselves:

1. **Saturday:** Noor checks a leaf on her daughter's phone, offline.
2. **Save now, send later:** the result goes to the co-op as one SMS.
3. **At the co-op:** the alert, the map and the officer's visit list.
4. **Harvest:** Noor texts `PRICE` (or `BEI`) from her basic phone.

Button names below are the exact English labels in the app and the hub (from [content/cards.json](content/cards.json)
and the hub pages). English is the app's main language. Every screen is also available in Kiswahili and Gĩkũyũ,
and the result screen can play the advice in all three languages.

Honesty labels you will see on screen, and should leave visible:

- **DEMO** ("DEMO: sample data"): invented members and prices.
- **SIMULATED** ("SMS SIMULATED", "SIMULATED: no real SMS was sent"): no real SMS is sent.
- **UNVERIFIED**: no person has checked that text or audio yet (in Kiswahili *HAIJAHAKIKIWA*, in Gĩkũyũ
  *NDĨRATHUTHURIO*).

The DEMO story (from [hub/seed.py](hub/seed.py)), set in Kirinyaga County, Kenya:

- Noor is member **M0123** of the Ondera Farmers' Co-operative Society, in *Ondera Juu*, a fictional community. Her
  phone is **+254700000123** (DEMO) and her SMS language is English.
- Two neighbours, Peter Mwangi Kariuki (M0105) and Mary Wambui Ndungu (M0108), reported rust in the last 7 days.
- So Noor's rust report is the **3rd within 5 km in 7 days**, and that fires the outbreak alert.

## 0. What you need

| Role | Device | What runs there |
|---|---|---|
| Co-op hub | laptop | `./run.sh`, then the hub at http://localhost:8000/ |
| Daughter's smartphone | Android phone with Chrome, USB cable, `adb` on the laptop | the app at http://localhost:8000/app/ via `adb reverse` |
| Noor's basic phone | the hub's **SMS simulator** page on the laptop | SIMULATED |

No Android phone? Use the [laptop-only fallback](#laptop-only-fallback) at the end.

## 1. Preparation (before you record)

1. **Start the hub:** `./run.sh` (on macOS: `PYTHON=python3.11 ./run.sh` the first time; see
   [README.md](README.md#quick-start-8-steps)).
2. **Reset the DEMO data.** On http://localhost:8000/, press **"Reset DEMO data"** and confirm. You can also
   run `curl -X POST http://localhost:8000/api/demo/reset`. The DEMO reports are dated relative to the day of
   seeding, so a database from an earlier day may no longer fire the alert.
3. **Get the field photos, then copy the demo photos to the phone.** The two field rust photos are CC BY-NC, so
   they are not in the repository. Download them once, with internet:
   ```
   python3 model/demo_samples.py --field
   adb push model/demo_samples/field/roya_field_1.jpg /sdcard/Download/
   adb push model/demo_samples/roya_1.jpg /sdcard/Download/
   adb push model/demo_samples/blurred_roya.jpg /sdcard/Download/
   ```
4. **Why these photos:**
   - **roya_field_1.jpg** (main demo) is a real field photo of leaf rust from Latin America, from iNaturalist
     (© jpgalvan, CC BY-NC, https://www.inaturalist.org/photos/31642233). It is from the held-out field test: the
     model never trained on this observer's photos. We picked it because the app answers it correctly. It shows
     what the app can do on a clear field photo, not how often: on the held-out field rust photos the shipped
     model is right in 34 of 53 (64%), and the rest get "I'm not sure"
     ([reports/field_eval.md](reports/field_eval.md)). **We have no Kenyan field photo of rust:** none of the 219
     iNaturalist rust photos we used is from East Africa. If the photo appears in the video, show the credit line.
   - **roya_1.jpg** (backup) is a Kenyan lab close-up from the JMuBEN test split (JMuBEN was photographed in
     Kirinyaga, per the dataset paper). Use it if the field photo is missing.
   - **blurred_roya.jpg** is roya_1.jpg, blurred.
   - In the real app page (desktop Chromium), roya_field_1.jpg gave **Leaf rust 99%**, roya_1.jpg gave **Leaf
     rust 99%**, and blurred_roya.jpg gave the fail-safe with "The photo is blurry."
     ([reports/model_demo_samples_check.json](reports/model_demo_samples_check.json)).
   - Other samples, one per class, are in [model/demo_samples/](model/demo_samples/README.md). The optional
     `field_whole_tree.jpg` is a real photo of a sick tree taken from too far away: the app says "I'm not sure"
     (it takes the distant tree for "not a coffee leaf").
5. **Connect the phone:** USB debugging on, cable in, then `adb reverse tcp:8000 tcp:8000`.
6. **Load the app once while online.** On the phone, open **http://localhost:8000/app/** in Chrome. Wait for the
   green label **"Ready to use without internet"**. Everything is now cached: app, model, cards, audio in all three
   languages.
   - Stop on the first screen ("Choose your language"), so the video can show the onboarding.
   - If the phone was used before, go to **"Settings"** → **"Delete all"** → **"Yes, delete all"**. This wipes
     the records and settings and keeps the offline cache.
7. **Go offline:** turn on airplane mode **and unplug the USB cable**. `adb reverse` works over USB, so with the
   cable in, the phone could still reach the hub. Reload the page: it opens from the cache.

## 2. Saturday scene: Noor checks a leaf (phone, offline)

1. **"Choose your language".** There are three buttons: **"English"**, **"Kiswahili"** and **"Gĩkũyũ"**. Tap
   **"English"**, then **"Continue"**.
   - Tapping a language says "choose your language" in that language ("Chagua lugha yako", "Thuura rũthiomi
     rwaku"). The next two screens read themselves aloud, if the browser allows it.
   - To show the whole interface in Gĩkũyũ or Kiswahili, tap that language instead. You can also switch later in
     "Settings" → "Language".
   - Whatever the interface language, the result screen has a "Listen in …" button for each of the three
     languages.
2. **"Your permission"** (consent). The text says what is stored and that nothing is sent without a tap. Tap **"Yes,
   I agree"**. ("No, thank you" goes back and stores nothing.)
3. **Member number** ("Your member number (example: M0123)"):
   - The "M" is already there: type **0123**.
   - Leave the PIN ("4-number PIN (if you want)") empty, or set 4 digits to show the lock.
   - Tap **"Continue"**.
4. **Location prompt from Chrome: choose "Don't allow" / "Block".** The SMS then carries `-` and the hub uses
   Noor's registered plot in Ondera Juu. If you allow it, the report lands where you really are, and the alert
   will not fire.
5. **Home screen.** Point at the two tips:
   - *"Take the photo under the leaf, up close: let the spot fill the photo. Use good light."*
   - *"No phone in the coffee field? Bring a few leaves home and take the photo there."*
6. Tap **"Choose a photo"** → Downloads → **roya_field_1.jpg** (backup: **roya_1.jpg**). ("Take photo" opens the
   camera.)
   - **Say on camera:** this is a real field photo of rust from Latin America that the model never trained on; we
     have no Kenyan field photo yet. On field photos like it, our model names rust about two times in three;
     otherwise it says "I'm not sure". It can also be wrong, so the officer confirms.
   - With roya_1.jpg, say instead: this is a Kenyan lab close-up from the test set, not a field photo.
7. **"Checking the leaf…"** appears. The first photo takes a few seconds while the runtime and model load from the
   cache (3.7 s in our emulated phone, one cold run; [reports/browser_metrics.md](reports/browser_metrics.md)).
8. **Result:**
   - **"Leaf rust"**, *"It looks like coffee leaf rust."*, and the **"How sure"** bar (99%).
   - The English audio starts by itself if the browser allows it. Otherwise tap **"Listen in English"**.
   - Then tap **"Listen in Gĩkũyũ"**, then **"Listen in Kiswahili"**. Each button stops the audio before it.
   - Point at the **UNVERIFIED** badges: the Kiswahili and Gĩkũyũ texts are AI drafts, and their audio is an
     English synthetic voice reading them. A native speaker must review and record them (section 4).
9. **Scroll down:**
   - **"What to do this week"**: the rust advice (check under the leaves every week, prune, ask the officer about
     spraying before the rains and about resistant varieties such as Ruiru 11 and Batian), plus when to call the
     officer.
   - The limits note: the app only looks at leaves. It cannot see coffee berry disease on the berries, antestia
     bugs, berry borer, lack of fertiliser, drought, old trees or soil problems.
   - **"Saved on this phone"**.
10. **Fail-safe, blurred photo:** tap **"Take photo"** in the bottom bar → **"Choose a photo"** →
    **blurred_roya.jpg**. Expected:
    - **"Not sure"**
    - *"I'm not sure — show the leaf to the extension officer."*
    - *"The photo is blurry."*
    - How sure 0%
11. **Fail-safe, not a coffee leaf:** tap **"Another photo"** and photograph an object, such as a cup. **Do not
    photograph a person:** step 3.6 uploads this photo to the hub too. Expected: the same *"I'm not sure…"*
    with *"It does not look like a coffee leaf."* Our tests checked this with test images, not with a live phone
    camera: 98.2% of non-coffee test images were rejected. The 8 of 446 that were not are mostly apple leaves with
    rust or scab, answered as rust ([reports/model_eval.md](reports/model_eval.md)). So point the camera at an
    object, not at another plant's leaf.
12. **"My checks"**: the three checks, each marked **"Not sent yet"**.

## 3. Save now, send later

1. In "My checks", tap the **Leaf rust** row. Under *"This is the message that will be sent:"* is the code, e.g.
   `CAF1 M0123 RUST 99 20261004 - #K3F9`. It is one SMS of plain characters, so it works on 2G.
2. Tap **"Send by SMS"**. The phone's own SMS app opens with the code, addressed to the DEMO number
   `+254700000000`.
   - **Do not press send:** the number is a placeholder.
   - Go back to Cafetal. It asks whether you sent it: **"Cancel"** / **"Sent"**. Tap **"Cancel"**.
   - Nothing is ever sent without the user's tap.
3. **Arrive at the co-op.** Plug the USB cable back in and run `adb reverse tcp:8000 tcp:8000` again. In this
   demo, this stands in for the co-op's Wi-Fi.
4. Open **"My checks"** again and tap the **Leaf rust** row. The app checks for the hub each time a result opens.
   A blue box appears.
5. Tap **"Send (SIMULATED)"**. You should see:
   - the hub's reply: *"Cafetal: we got your report. Thank you. The extension officer checks the visit list. If it
     is urgent, call the co-op."*
   - the chip **"SIMULATED: no real SMS was sent"**
   - the status **"Sent"**
6. Tap **"Send photos to the co-op (Wi-Fi)"**. You should see **"Photos sent to the co-op"**. The photo now appears
   on the officer's list.
   - **Note:** this one tap sends **every record on the phone not yet sent to the hub, photos included**, not
     just the open one. Here that is also the blurred photo and the not-coffee photo from steps 2.10–2.11. There is
     no per-photo choice.

## 4. At the co-op: the hub (laptop, http://localhost:8000/)

1. **"Home"** shows:
   - under "Active outbreak alerts": **"Rust near Ondera Juu: 3 members reported rust in 7 days"**
   - the **"Waiting for approval"** count
   - the box "Rules (design choices, not agronomic thresholds)"
   - the "Reference price (not AI)" table, marked DEMO
2. **"Outbox"** shows **"Outbreak alert #1 — 24 messages"**, one alert SMS per member.
   - Each SMS is the card `alert_roya` in the member's SMS language (English, Kiswahili or Gĩkũyũ), marked
     UNVERIFIED, 1 SMS long.
   - Type a name in **"Who approves:"**.
   - Press **"Approve all 24"** and confirm. "Reject all 24" and per-row "Approve" / "Reject" buttons also exist.
   - To approve a single message instead, use **"Approve"** on the row **"Noor (DEMO)"**, phone +254700000123. It
     is the second row, **not** the first (that is Joyce Gathoni Kinyua, M0124). The next step ("SMS simulator")
     shows Noor's alert only once her own message is approved.
   - Nothing went out until this tap.
3. **"SMS simulator"**: Noor's basic phone now shows the alert *"CO-OP ALERT: 3 leaf rust reports near Ondera Juu
   this week. Check under the leaves and tell the co-op."*, tagged "ALERT". It also shows her earlier report and
   the reply.
4. **"Map"**: Noor's plot is inside the red circle **"Alert #1"** (5 km), in Ondera Juu. Every dot has the colour of
   that farm's most serious report in 30 days. It is a plain SVG map, with no internet and no roads.
5. **"Officer worklist"** (the "Extension officer's visit list"):
   - Noor is **#1**: *"Rust 99% · alert area · … · with photo"*, with the leaf photo (the percentage is the one in
     your SMS code). The banner says **"You decide whom to visit."**
   - Press **"Visit scheduled"**.
   - After the visit, the officer picks the true label in the drop-down (set at first to the app's answer, "Leaf
     rust"). Then press **"Confirmed"** (or "Not confirmed" with a different label) and add an optional note.
   - The row appears under **"Checked examples (for retraining the model)"**. Officer-confirmed photos from
     Kirinyaga farms are what the model needs to work in the field.
6. **"Content"** (content review):
   - **Verify a card:** type a name and role in **"Who reviews"**. Search `diag_roya` and press **"Mark verified"**
     under English. The badge changes to "verified" and shows the name.
   - **Record native audio:** type a name in **"Who records (native voice)"**. Press **"● Record"** under Gĩkũyũ,
     speak, then press **"■ Stop and save"**. Recording needs this page at `localhost` or HTTPS; otherwise use
     **"Upload file"**.
   - The audio is marked "native voice". It stays UNVERIFIED until someone listens and marks it.
   - The phone gets new text and audio the next time it is online at the co-op.
   - **Warning:** this writes to `content/cards.json` and `content/audio/` in the repository. "Reset DEMO data"
     does **not** undo it. After a rehearsal, run `git checkout -- content/` unless it was a real review.

## 5. Harvest scene: Noor's basic phone (SMS simulator)

1. Open **"SMS simulator"**. The phone selected under **"Phone"** is *"Noor (DEMO) · M0123 · +254700000123"*.
2. Press **"PRICE"**. The reply is *"Reference price 2026: coffee 139.00 KES/kg cherry, maize 51.11, beans 111.11
   KES/kg. Source: DEMO county 25/26, KAMIS. Not the price at your factory."* Say it: these are **DEMO** reference
   prices (the coffee figure is the Kirinyaga county average paid per kg of cherry in the 2025/26 season), not AI,
   and never the price at Noor's own factory or farm gate.
3. Press **"BEI"** (the Kiswahili keyword). The reply is the same, in English, because replies follow the member's
   registered SMS language and Noor's is English. To see it in Kiswahili, choose *"Mary Wambui Ndungu (DEMO) ·
   M0108 · +254700000108"* under "Phone" and press "BEI": *"Bei elekezi 2026: kahawa 139.00 KES/kg cherry, mahindi
   51.11, maharagwe 111.11 KES/kg. Chanzo: DEMO county 25/26, KAMIS. Si bei ya kiwanda chako."* Then switch back
   to Noor.
4. **Free text:** type `how much are you paying for a kilo of cherry` and press **"Send"**.
   - The right panel, "What the hub did with the last message", shows intent **price** with its confidence.
   - The reply is the same price card. In Kiswahili, `bei ya kahawa ni ngapi` does the same.
   - The **"text: talk to officer"**, **"text: report"** and **"text: report (Kiswahili)"** buttons send other
     examples. They also go to the officer's inbox: a free-text symptom report gets the how-to-report card *and*
     reaches the officer.
5. **Unknown message → officer:** type `there was hail yesterday and many berries fell` (berries, which the app
   cannot see) and press **"Send"**.
   - The panel shows intent **other** (confidence 88% when we ran it) and "Message passed to the officer."
   - Noor gets *"Cafetal: we are passing your message to the extension officer. The officer or the co-op will answer
     you."*
   - On **"Officer worklist"**, the message is under **"Messages from members for the officer"**. The officer calls
     back; the system never sends free text to members.
6. Optional:
   - Choose *"Peter Mwangi Kariuki (DEMO) · M0105"*, a Gĩkũyũ-registered member, and press "PRICE" to see the
     Gĩkũyũ SMS (UNVERIFIED; in SMS, ĩ and ũ are written i and u): *"Thogora wa kuonereria 2026: kahua 139.00
     KES/kg cherry, …"*.
   - Choose *"NOT registered number · +254799000000"* to see *"Cafetal: this number is not registered. Please visit
     the co-op office to sign up."*
   - The other keywords: `HELP` or `MSAADA` (the list of keywords), `OFFICER` or `AFISA` (passes the message to the
     officer). There are no Gĩkũyũ keywords. "Registration" can register a member with English, Kiswahili or
     Gĩkũyũ as SMS language.

## 6. After the demo

- Press **"Reset DEMO data"** so the next run can fire the alert again.
- If you verified or recorded cards only for practice, run `git checkout -- content/`.
- Stop the hub with Ctrl+C. To get fresh DEMO dates the next time `./run.sh` starts, run `rm hub/cafetal.db*`.

## What can go wrong (checklist)

- [ ] **No alert fires:**
  - **Stale DEMO dates:** the neighbours' reports are older than 7 days → reset the DEMO data.
  - **Alert already fired in a rehearsal** (at most one per area per 7 days) → reset.
  - **Location allowed on the phone:** the report is placed where you really are → block location for
    `localhost:8000` in Chrome (address bar → site settings), then send a new photo.
- [ ] **The phone shows an old version of the app.** `run.sh` sets a new offline-cache version whenever a
      cached file changes. Reload the app once while online. If that fails, Chrome → site settings → clear data
      for localhost:8000 and load it again.
- [ ] **"Ready to use without internet" never appears:**
  - You opened the app as `http://<laptop-ip>:8000`. That is not a secure origin, so there is no offline cache
    and no location. Use `adb reverse` and `http://localhost:8000/app/`, an HTTPS host, or the Chrome flag (demo
    only; see [README.md](README.md#why-localhost-or-https-the-secure-origin-rule)).
  - Or the first download did not finish. Stay online and wait.
- [ ] **"Offline" still reaches the hub.** `adb reverse` works over USB, even in airplane mode. Unplug the cable
      for the offline part, then plug it back in and run `adb reverse tcp:8000 tcp:8000` again.
- [ ] **No "Send (SIMULATED)" button.** The hub is not reachable from the phone. Check
      http://localhost:8000/api/health in the phone's Chrome, then reopen the record from "My checks".
- [ ] **No sound.** The browser blocked autoplay: tap "Listen in English", "Listen in Gĩkũyũ" or "Listen in
      Kiswahili". Check the phone is not on silent.
- [ ] **A live photo of a real coffee leaf** may get an answer or "I'm not sure". Both are expected: on held-out
      field rust photos (from the Americas) the shipped model answered rust in 64% and "I'm not sure" in the rest,
      and it gave a disease answer to 2.5% of ordinary coffee-plant photos (false alarms;
      [reports/field_eval.md](reports/field_eval.md)). Don't promise a diagnosis on a live leaf: say the officer
      confirms. A live "Leaf rust" answer sent to the hub fires the outbreak alert just like the demo photo, so try
      live leaves only after the main demo, or reset the DEMO data afterwards.
- [ ] **roya_field_1.jpg is missing.** Run `python3 model/demo_samples.py --field` on a machine with internet,
      or use roya_1.jpg and say it is a Kenyan lab close-up.
- [ ] **The phone already has another member or old records** → "Settings" → "Delete all" → "Yes, delete all".
- [ ] **Port 8000 is busy** → `PORT=9000 ./run.sh`, then `adb reverse tcp:9000 tcp:9000` and
      http://localhost:9000/app/.
- [ ] **The photo is not in the phone's picker.** Use the picker's file browser (Downloads). Or push the file to
      `/sdcard/Pictures/` instead.

## Laptop-only fallback

You can do the whole journey in desktop Chrome on the hub laptop:

1. Open http://localhost:8000/app/ with DevTools in device mode (for example, Pixel). `localhost` is a secure
   origin.
2. Wait for "Ready to use without internet".
3. **Offline:** stop `./run.sh` with Ctrl+C, so nothing answers on port 8000. Reload the app: it opens from the
   cache. Do section 2, choosing the files from `model/demo_samples/` (the field photo is in
   `model/demo_samples/field/`). Block location when Chrome asks, for the same reason as on the phone.
4. Start `./run.sh` again. The database is kept, not re-seeded. Then do sections 3–5. Skip the "Send by SMS"
   step; a laptop has no SMS app.

The automated version of this journey is `node tests/e2e/journey.mjs`. It resets the DEMO data before and after.

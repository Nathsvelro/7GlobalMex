# Cafetal demo, click by click

This is the whole journey for the 2–5 minute video and for judges trying Cafetal themselves:

1. **Saturday:** Noor checks a leaf on her daughter's phone, offline.
2. **Save now, send later:** the result goes to the co-op as one SMS.
3. **At the co-op:** the alert, the map and the officer's visit list.
4. **Harvest:** Noor texts `PRECIO` from her basic phone.

Button names below are the exact Spanish labels in the app and the hub. The English in brackets is only for you.

Honesty labels you will see on screen, and should leave visible:

- **DEMO**: invented members and prices.
- **SIMULADO**: no real SMS is sent.
- **SIN VERIFICAR**: no person has checked that text or audio yet.

The DEMO story (from [hub/seed.py](hub/seed.py)):

- Noor is member **M0123** in *Ondera Alto*, a fictional community.
- Two neighbours, M0105 and M0108, reported rust in the last 7 days.
- So Noor's rust report is the **3rd within 5 km in 7 days**, and that fires the outbreak alert.

## 0. What you need

| Role | Device | What runs there |
|---|---|---|
| Co-op hub | laptop | `./run.sh`, then the hub at http://localhost:8000/ |
| Daughter's smartphone | Android phone with Chrome, USB cable, `adb` on the laptop | the app at http://localhost:8000/app/ via `adb reverse` |
| Noor's basic phone | the hub's **Simulador SMS** page on the laptop | SIMULATED |

No Android phone? Use the [laptop-only fallback](#laptop-only-fallback) at the end.

## 1. Preparation (before you record)

1. **Start the hub:** `./run.sh`.
2. **Reset the DEMO data.** On http://localhost:8000/, press **"Reiniciar datos DEMO"** and confirm. You can also
   run `curl -X POST http://localhost:8000/api/demo/reset`. The DEMO reports are dated relative to the day of
   seeding, so a database from an earlier day may no longer fire the alert.
3. **Copy the demo photos to the phone:**
   ```
   adb push model/demo_samples/roya_1.jpg /sdcard/Download/
   adb push model/demo_samples/blurred_roya.jpg /sdcard/Download/
   ```
4. **Why these two photos:**
   - **roya_1.jpg** is a held-out JMuBEN test image: a Kenyan close-up the model never trained on. The shipped
     model only recognises close-ups like its training crops. On field photos it almost always answers "No estoy
     seguro" ([reports/field_eval.md](reports/field_eval.md): 0 of 219 iNaturalist rust photos answered
     correctly).
   - **blurred_roya.jpg** is the same leaf, blurred.
   - In the real app page (desktop Chromium), roya_1.jpg gave **Roya 99%** and blurred_roya.jpg gave the
     fail-safe with "La foto salió borrosa".
   - Other samples, one per class, are in [model/demo_samples/](model/demo_samples/README.md).
5. **Connect the phone:** USB debugging on, cable in, then `adb reverse tcp:8000 tcp:8000`.
6. **Load the app once while online.** On the phone, open **http://localhost:8000/app/** in Chrome. Wait for the
   green label **"Listo para usar sin internet"**. Everything is now cached: app, model, cards, audio.
   - Stop on the first screen ("Elija su idioma"), so the video can show the onboarding.
   - If the phone was used before, go to **"Ajustes"** → **"Borrar todo"** → **"Sí, borrar todo"**. This wipes
     the records and settings and keeps the offline cache.
7. **Go offline:** turn on airplane mode **and unplug the USB cable**. `adb reverse` works over USB, so with the
   cable in, the phone could still reach the hub. Reload the page: it opens from the cache.

## 2. Saturday scene: Noor checks a leaf (phone, offline)

1. **"Elija su idioma"** (choose your language). Tap **"Español"**, then **"Seguir"**.
   - Tapping a language says "choose your language" in that language. The next two screens read themselves
     aloud, if the browser allows it.
   - To show the whole interface in Tseltal, tap **"Bats'il k'op (Tseltal)"** instead. You can also switch later
     in "Ajustes" → "Idioma".
2. **"Su permiso"** (consent). The text says what is stored and that nothing is sent without a tap. Tap **"Sí,
   acepto"**. ("No, gracias" goes back and stores nothing.)
3. **Member number:**
   - The "M" is already there: type **0123**.
   - Leave the PIN empty, or set 4 digits to show the lock.
   - Tap **"Seguir"**.
4. **Location prompt from Chrome: choose "Don't allow" / "Block".** The SMS then carries `-` and the hub uses
   Noor's registered plot in Ondera Alto. If you allow it, the report lands where you really are, and the alert
   will not fire.
5. **Home screen.** Point at the two tips:
   - *"Tome la foto por debajo de la hoja, de cerca…"* (photograph the underside of the leaf, close up)
   - *"¿No lleva el teléfono al cafetal? Traiga unas hojas a la casa…"* (no phone in the field? bring leaves home)
6. Tap **"Elegir una foto"** (choose a photo) → Downloads → **roya_1.jpg**. ("Tomar foto" opens the camera.)
   - **Say on camera:** this is a test close-up the model never trained on, and on real field photos our model
     still says "No estoy seguro".
7. **"Revisando la hoja…"** appears. The first photo takes a few seconds while the runtime and model load from the
   cache (2.6 s in our emulated phone; [reports/browser_metrics.md](reports/browser_metrics.md)).
8. **Result:**
   - **"Roya"**, *"Parece roya del cafeto."*, and the **"Seguridad"** (confidence) bar.
   - The audio starts by itself if the browser allows it. Otherwise tap **"Escuchar en tseltal"**, then
     **"Escuchar en español"**.
   - Point at the **SIN VERIFICAR** badges: the Tseltal text is an AI draft, and its audio is a Spanish synthetic
     voice reading it. A native speaker must record it (section 4).
9. **Scroll down:**
   - **"Qué hacer esta semana"** (what to do this week): the rust advice, plus when to call the officer.
   - The limits note: the app only sees leaves, not broca, fertiliser, drought or soil.
   - **"Guardado en este teléfono"** (saved on this phone).
10. **Fail-safe, blurred photo:** tap **"Tomar foto"** in the bottom bar → **"Elegir una foto"** →
    **blurred_roya.jpg**. Expected:
    - **"No seguro"**
    - *"No estoy seguro — muestre la hoja al técnico."* (I'm not sure, show the leaf to the officer)
    - *"La foto salió borrosa."* (the photo is blurry)
    - Seguridad 0%
11. **Fail-safe, not a coffee leaf:** tap **"Otra foto"** and photograph anything else, such as a cup or your
    hand. Expected: the same *"No estoy seguro…"* with *"No parece hoja de café."* (doesn't look like a coffee
    leaf). Our tests checked this with test images, not with a live phone camera: 99.8% of non-coffee test images
    were rejected ([reports/model_eval.md](reports/model_eval.md)).
12. **"Mis revisiones"** (my checks): the three checks, each marked **"Por enviar"** (to send).

## 3. Save now, send later

1. In "Mis revisiones", tap the **Roya** row. Under *"Este es el mensaje que se va a mandar:"* (this is the
   message that will be sent) is the code, e.g. `CAF1 M0123 ROYA 99 20261004 - #K3F9`. It is one SMS of plain
   characters, so it works on 2G.
2. Tap **"Enviar por SMS"**. The phone's own SMS app opens with the code, addressed to the DEMO number
   `+520000000000`.
   - **Do not press send:** the number is a placeholder.
   - Go back to Cafetal. It asks whether you sent it: **"Cancelar"** / **"Enviado"**. Tap **"Cancelar"**.
   - Nothing is ever sent without the user's tap.
3. **Arrive at the co-op.** Plug the USB cable back in and run `adb reverse tcp:8000 tcp:8000` again. In this
   demo, this stands in for the co-op's Wi-Fi.
4. Open **"Mis revisiones"** again and tap the **Roya** row. The app checks for the hub each time a result opens.
   A blue box appears.
5. Tap **"Enviar (SIMULADO)"**. You should see:
   - the hub's reply: *"Cafetal: recibimos su reporte. Gracias. El tecnico revisa la lista de visitas…"*
   - the chip **"SIMULADO: no se mandó un SMS de verdad"** (no real SMS was sent)
   - the status **"Enviado"**
6. Tap **"Mandar fotos a la cooperativa (Wi-Fi)"** (send photos to the co-op). You should see **"Fotos enviadas a
   la cooperativa"**. The photo now appears on the officer's list.

## 4. At the co-op: the hub (laptop, http://localhost:8000/)

1. **"Inicio"** (home) shows:
   - under "Avisos de brote activos" (active outbreak alerts): **"Roya cerca de Ondera Alto: 3 socios reportaron
     roya en 7 días"**
   - the **"Por aprobar"** (to approve) count
   - the rules box, which says the parameters are design choices, not agronomic thresholds
2. **"Bandeja de salida"** (outbox) shows **"Aviso de brote #1 — 24 mensajes"**, one alert SMS per member.
   - Each SMS is a card: `alert_roya` in Spanish or Tseltal, marked SIN VERIFICAR, 1 SMS long.
   - Type a name in **"Quién aprueba"** (who approves).
   - Press **"Aprobar los 24"** and confirm, or **"Aprobar"** on a single row. "Rechazar" also exists.
   - Nothing went out until this tap.
3. **"Simulador SMS"**: Noor's basic phone now shows the alert *"AVISO DE LA COOPERATIVA: 3 reportes de roya
   cerca de Ondera Alto esta semana…"*, tagged "AVISO". It also shows her earlier report and the reply.
4. **"Mapa"** (map): Noor's plot is inside the red circle **"Aviso #1"** (5 km). Every dot has the colour of
   that farm's most serious report in 30 days. It is a plain SVG map, with no internet and no streets.
5. **"Técnico"** (officer):
   - Noor is **#1**: *"Roya 99% · zona de alerta · … · con foto"*, with the leaf photo. The banner says **"Usted
     decide a quién visitar"** (you decide whom to visit).
   - Press **"Visita programada"** (visit scheduled).
   - After the visit, the officer picks the true label in **"Etiqueta real…"** (set at first to the app's
     answer). Then press **"Confirmado"** (or "No confirmado" with a different label) and add an optional note.
   - The row appears under **"Ejemplos revisados (para reentrenar el modelo)"** (reviewed examples, for
     retraining). Officer-confirmed Chiapas photos are what the model needs to work in the field.
6. **"Contenido"** (content review):
   - **Verify a card:** type a name and role in **"Quién revisa"** (who reviews). Search `diag_roya` and press
     **"Marcar verificado"** (mark as verified) under Español. The badge changes to "verificado" and shows the
     name.
   - **Record native audio:** type a name in **"Quién graba (voz nativa)"** (who records). Press **"● Grabar"**
     (record) under Tseltal, speak, then press **"■ Detener y guardar"** (stop and save). Recording needs this page
     at `localhost` or HTTPS; otherwise use **"Subir archivo"** (upload a file).
   - The audio is marked "voz nativa" (native voice). It stays SIN VERIFICAR until someone listens and marks it.
   - The phone gets new text and audio the next time it is online at the co-op.
   - **Warning:** this writes to `content/cards.json` and `content/audio/` in the repository. "Reiniciar datos
     DEMO" does **not** undo it. After a rehearsal, run `git checkout -- content/` unless it was a real review.

## 5. Harvest scene: Noor's basic phone (Simulador SMS)

1. Open **"Simulador SMS"**. The phone selected under **"Teléfono"** is *"Noor (DEMO) · M0123 · +529670000123"*.
2. Press **"PRECIO"**. The reply is *"Precio de referencia sept 2026: cafe pergamino 94.00 MXN/kg, maiz 9.00,
   frijol 24.90 MXN/kg. Fuente: DEMO ICE/Banxico/SNIIM. No es el precio de su comunidad."* Say it: these are
   **DEMO** reference prices, not AI, and never the farm-gate price.
3. **Free text:** type `cuanto estan pagando el kilo de cafe` and press **"Enviar"**.
   - The right panel, "Qué hizo el hub con el último mensaje" (what the hub did), shows intent **precio** with its
     confidence.
   - The reply is the same price card.
   - The **"texto: hablar con técnico"** and **"texto: reporte"** buttons send other examples.
4. **Unknown message → officer:** type `se secaron mis matas con el calor que hago` (drought, which the app
   cannot see) and press **"Enviar"**.
   - The panel shows the intent is below the threshold, *"pasa al técnico"* (goes to the officer).
   - Noor gets *"Cafetal: le paso su mensaje al tecnico…"* (I'll pass your message to the officer).
   - On **"Técnico"**, the message is under **"Mensajes de socios para el técnico"**. The officer calls back; the
     system never sends free text to members.
5. Optional:
   - Choose *"Pedro López Hernández (DEMO) · M0105"*, a Tseltal-registered member, and press "PRECIO" to see the
     Tseltal SMS (SIN VERIFICAR).
   - Choose *"Número NO registrado"* to see the "please register at the co-op" reply.

## 6. After the demo

- Press **"Reiniciar datos DEMO"** so the next run can fire the alert again.
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
- [ ] **"Listo para usar sin internet" never appears:**
  - You opened the app as `http://<laptop-ip>:8000`. That is not a secure origin, so there is no offline cache
    and no location. Use `adb reverse` and `http://localhost:8000/app/`, an HTTPS host, or the Chrome flag (demo
    only; see [README.md](README.md#why-localhost-or-https-the-secure-origin-rule)).
  - Or the first download did not finish. Stay online and wait.
- [ ] **"Offline" still reaches the hub.** `adb reverse` works over USB, even in airplane mode. Unplug the cable
      for the offline part, then plug it back in and run `adb reverse tcp:8000 tcp:8000` again.
- [ ] **No "Enviar (SIMULADO)" button.** The hub is not reachable from the phone. Check
      http://localhost:8000/api/health in the phone's Chrome, then reopen the record from "Mis revisiones".
- [ ] **No sound.** The browser blocked autoplay: tap "Escuchar en tseltal" / "Escuchar en español". Check the
      phone is not on silent.
- [ ] **A live photo of a real coffee leaf says "No estoy seguro".** This is expected with the shipped model
      (see [reports/field_eval.md](reports/field_eval.md)). Present it as the fail-safe working, and don't
      promise a diagnosis on a live leaf.
- [ ] **The phone already has another member or old records** → "Ajustes" → "Borrar todo" → "Sí, borrar todo".
- [ ] **Port 8000 is busy** → `PORT=9000 ./run.sh`, then `adb reverse tcp:9000 tcp:9000` and
      http://localhost:9000/app/.
- [ ] **The photo is not in the phone's picker.** Use the picker's file browser (Downloads). Or push the file to
      `/sdcard/Pictures/` instead.

## Laptop-only fallback

You can do the whole journey in desktop Chrome on the hub laptop:

1. Open http://localhost:8000/app/ with DevTools in device mode (for example, Pixel). `localhost` is a secure
   origin.
2. Wait for "Listo para usar sin internet".
3. **Offline:** stop `./run.sh` with Ctrl+C, so nothing answers on port 8000. Reload the app: it opens from the
   cache. Do section 2, choosing the files from `model/demo_samples/`. Block location when Chrome asks, for the
   same reason as on the phone.
4. Start `./run.sh` again. The database is kept, not re-seeded. Then do sections 3–5. Skip the "Enviar por SMS"
   step; a laptop has no SMS app.

The automated version of this journey is `node tests/e2e/journey.mjs`. It resets the DEMO data before and after.

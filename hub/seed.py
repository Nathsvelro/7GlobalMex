"""DEMO data for the hub: 24 fictional members in 4 fictional "Ondera" communities (Kirinyaga County, central Kenya,
Mt Kenya coffee belt) and ~20 days of observations relative to today. Every seeded row has demo=1 and every name
says (DEMO). Noor, the Ondera Farmers' Co-operative Society and the Ondera communities are made up.

    python -m hub.seed --if-missing    # seed only if the database file does not exist yet (run.sh does this)
    python -m hub.seed --reset         # wipe everything and seed again (same as POST /api/demo/reset)

The demo story: two other members near Noor (M0123, Ondera Juu) reported RUST in the last 7 days. When Noor
sends her own RUST code, hers is the 3rd report within 5 km in 7 days and the outbreak alert fires.
"""
import argparse
from datetime import datetime, time, timedelta

from . import cards, db, intent, sms

COMMUNITIES = {  # fictional names and centres (lat, lon), Kirinyaga County, Kenya
    "Ondera Juu": (-0.515, 37.320),
    "Ondera Chini": (-0.562, 37.380),
    "Ondera Mto": (-0.465, 37.225),
    "Ondera Kilima": (-0.465, 37.378),
}

# member number, name, community, lat, lon, SMS language (en | sw | kik). All names are made up.
MEMBERS = [
    (123, "Noor", "Ondera Juu", -0.518, 37.322, "en"),
    (101, "Grace Wanjiru Muriuki", "Ondera Juu", -0.526, 37.306, "en"),
    (105, "Peter Mwangi Kariuki", "Ondera Juu", -0.506, 37.312, "kik"),
    (108, "Mary Wambui Ndungu", "Ondera Juu", -0.531, 37.329, "sw"),
    (112, "Joseph Kamau Gitau", "Ondera Juu", -0.513, 37.336, "kik"),
    (116, "Lucy Njeri Wachira", "Ondera Juu", -0.509, 37.327, "en"),
    (102, "Samuel Maina Kinyua", "Ondera Chini", -0.564, 37.374, "sw"),
    (106, "Esther Wairimu Mugo", "Ondera Chini", -0.556, 37.389, "kik"),
    (109, "James Njoroge Waweru", "Ondera Chini", -0.569, 37.382, "en"),
    (113, "Margaret Nyambura Kimani", "Ondera Chini", -0.552, 37.371, "sw"),
    (117, "Daniel Githinji Murage", "Ondera Chini", -0.561, 37.393, "kik"),
    (120, "Agnes Wangari Macharia", "Ondera Chini", -0.573, 37.369, "sw"),
    (103, "Stephen Ngugi Karanja", "Ondera Mto", -0.468, 37.225, "kik"),
    (107, "Faith Muthoni Kibe", "Ondera Mto", -0.459, 37.237, "en"),
    (110, "John Wachira Maina", "Ondera Mto", -0.472, 37.216, "sw"),
    (114, "Catherine Wangui Njagi", "Ondera Mto", -0.454, 37.222, "kik"),
    (118, "Francis Mutua Musyoka", "Ondera Mto", -0.477, 37.234, "sw"),
    (121, "Jane Wanjiku Ireri", "Ondera Mto", -0.463, 37.209, "en"),
    (104, "Paul Kimani Nyaga", "Ondera Kilima", -0.468, 37.374, "sw"),
    (111, "Purity Wacera Gathogo", "Ondera Kilima", -0.459, 37.386, "kik"),
    (115, "Patrick Kariuki Mbogo", "Ondera Kilima", -0.472, 37.391, "en"),
    (119, "Beatrice Mumbi Wahome", "Ondera Kilima", -0.455, 37.369, "kik"),
    (122, "Ann Achieng Otieno", "Ondera Kilima", -0.461, 37.363, "sw"),
    (124, "Joyce Gathoni Kinyua", "Ondera Kilima", -0.478, 37.382, "en"),
]

# member number, code, conf, days ago, obs id, location ("-" = plot), how it arrived
# conf: the app (model cafetal-img-v2, threshold 0.90 in app/model/labels.json) only sends HLTH/RUST/MINR/PHOM/CERC
# with conf >= 90; UNSR carries the model's top-1 below the threshold (0 = no model run). The outbreak rule counts
# RUST only at conf >= the threshold (hub/outbreak.py), so the two reports near Noor must be >= 90.
# No MITE: red spider mite is not in the model, so the app never sends it.
OBSERVATIONS = [
    # Ondera Juu: exactly two recent RUST reports near Noor (the demo trigger needs Noor's as the 3rd)
    (105, "RUST", 92, 2, "A1R2", (-0.51, 37.31), "sms"),
    (108, "RUST", 91, 4, "B7K4", (-0.53, 37.33), "sms"),
    (101, "HLTH", 91, 6, "C2M8", (-0.53, 37.31), "sms"),
    (112, "MINR", 92, 9, "D5P1", "-", "sms"),
    (116, "RUST", 93, 12, "E3T6", (-0.51, 37.33), "sms"),   # too old for the 7-day window
    (123, "HLTH", 96, 18, "F9N3", (-0.52, 37.32), "sms"),   # Noor's earlier check
    # Ondera Chini
    (102, "UNSR", 52, 3, "G4W7", (-0.56, 37.37), "sms"),
    (106, "CERC", 92, 5, "H8Q2", (-0.56, 37.39), "sms"),
    (109, "HLTH", 93, 8, "J1V5", "-", "sync"),
    (113, "PHOM", 91, 14, "K6X9", (-0.55, 37.37), "sms"),
    (120, "OTHR", 86, 10, "L2Z4", (-0.57, 37.37), "sms"),
    # Ondera Mto: one recent RUST, alone and far away (about 12 km from Noor: no alert)
    (103, "RUST", 95, 3, "M7B1", (-0.47, 37.22), "sms"),
    (107, "RUST", 90, 16, "N3C8", (-0.46, 37.24), "sms"),
    (110, "MINR", 94, 6, "P5D2", (-0.47, 37.22), "sms"),
    (114, "HLTH", 90, 11, "Q9F6", "-", "sms"),
    (118, "UNSR", 40, 1, "R4G3", (-0.48, 37.23), "sms"),
    # Ondera Kilima
    (104, "HLTH", 95, 2, "S8H7", (-0.47, 37.37), "sms"),
    (111, "CERC", 94, 7, "T2J5", (-0.46, 37.39), "sms"),
    (115, "MINR", 90, 13, "U6K1", (-0.47, 37.39), "sync"),
    (119, "UNSR", 0, 5, "V1L9", "-", "sms"),
    (122, "HLTH", 97, 19, "W5M4", (-0.46, 37.36), "sms"),
]

# member number, free text, days ago. Routed exactly like a real SMS: the label and confidence the officer sees
# come from the intent classifier (hub/intent_model.json) at seed time, not typed in here.
OFFICER_SMS = [
    (110, "afisa atakuja lini kijijini kwetu", 2),
    (109, "the coffee trees at the bottom dried up in the heat what do i do", 1),
]


def phone_for(n: int) -> str:
    return f"+254700000{n:03d}"


def at(days_ago: int, hour: int, base: datetime) -> str:
    d = (base - timedelta(days=days_ago)).date()
    return datetime.combine(d, time(hour, 15)).isoformat(timespec="seconds")


def seed(conn) -> dict:
    """Insert the DEMO data into an empty database. Returns counts."""
    now = db.now()
    with db.Tx(conn):
        for n, name, community, lat, lon, lang in MEMBERS:
            conn.execute(
                "INSERT INTO members(member_id, name, phone, community, lat, lon, language, consent, consent_date,"
                " consent_by, consent_text_version, created_at, demo) VALUES (?,?,?,?,?,?,?,1,?,?,?,?,1)",
                (f"M{n:04d}", f"{name} (DEMO)", phone_for(n), community, lat, lon, lang,
                 at(60, 10, now), "Co-op staff (DEMO)", "v1", at(60, 10, now)))
        members = {m["member_id"]: m for m in db.rows(conn.execute("SELECT * FROM members"))}

        for n, code, conf, days, obs_id, loc, source in OBSERVATIONS:
            mid = f"M{n:04d}"
            d = (now - timedelta(days=days)).date()
            loc_txt = "-" if loc == "-" else f"{loc[0]:.2f},{loc[1]:.2f}"
            raw = f"CAF1 {mid} {code} {conf} {d.strftime('%Y%m%d')} {loc_txt} #{obs_id}"
            rec = {"member_id": mid, "obs_id": obs_id, "code": code, "conf": conf, "date": d.isoformat(),
                   "lat": None if loc == "-" else loc[0], "lon": None if loc == "-" else loc[1],
                   "received_at": at(days, 18, now),
                   "model_version": "cafetal-img-v2" if code != "UNSR" or conf else None}
            sms.save_observation(conn, rec, source, raw_sms=raw if source == "sms" else None, demo=1)
            if source == "sms":
                m = members[mid]
                db.add_message(conn, "in", m["phone"], raw, "received", member_id=mid,
                               created_at=at(days, 18, now), demo=1)
                text, lang = cards.render("sms_obs_recibida", m["language"])
                db.add_message(conn, "out", m["phone"], text, "sent_simulated", member_id=mid,
                               card_id="sms_obs_recibida", lang=lang, created_at=at(days, 18, now), demo=1)

        # Noor asked for the price last week.
        noor = members["M0123"]
        db.add_message(conn, "in", noor["phone"], "PRICE", "received", member_id="M0123",
                       created_at=at(9, 19, now), demo=1)
        slots = sms.price_slots()
        card_id = "sms_precio" if slots else "sms_precio_sin_datos"
        text, lang = cards.render(card_id, noor["language"], **(slots or {}))
        db.add_message(conn, "out", noor["phone"], text, "sent_simulated", member_id="M0123", card_id=card_id,
                       lang=lang, created_at=at(9, 19, now), demo=1)

        n_officer = 0
        for n, body, days in OFFICER_SMS:
            mid = f"M{n:04d}"
            m = members[mid]
            cls = intent.classify(body)
            name = cls["intent"] if cls["accepted"] else "other"
            card_id = sms.INTENT_CARD.get(name, "sms_pasar_tecnico")
            msg_id = db.add_message(conn, "in", m["phone"], body, "received", member_id=mid,
                                    created_at=at(days, 7, now), demo=1)
            text, lang = cards.render(card_id, m["language"])
            db.add_message(conn, "out", m["phone"], text, "sent_simulated", member_id=mid,
                           card_id=card_id, lang=lang, created_at=at(days, 7, now), demo=1)
            if name in ("talk_to_officer", "other", "report"):   # same rule as hub/sms.py route()
                conn.execute(
                    "INSERT INTO officer_messages(message_id, member_id, phone, body, intent, conf, created_at, demo)"
                    " VALUES (?,?,?,?,?,?,?,1)",
                    (msg_id, mid, m["phone"], body, cls["intent"], cls["conf"], at(days, 7, now)))
                n_officer += 1
    return {"members": len(MEMBERS), "observations": len(OBSERVATIONS), "officer_messages": n_officer}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--if-missing", action="store_true", help="seed only if the database file does not exist")
    ap.add_argument("--reset", action="store_true", help="wipe the database and seed again")
    args = ap.parse_args()
    path = db.db_path()
    if args.if_missing and path.exists():
        print(f"hub database exists ({path}); not seeding. Use --reset to load the DEMO data again.")
        return
    conn = db.connect(path)
    if args.reset:
        db.wipe(conn)
    elif conn.execute("SELECT COUNT(*) FROM members").fetchone()[0]:
        print("database already has members; use --reset to wipe it first")
        return
    counts = seed(conn)
    print(f"DEMO data loaded into {path}: {counts}")


if __name__ == "__main__":
    main()

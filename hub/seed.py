"""DEMO data for the hub: 24 fictional members in 4 fictional "Ondera" communities (Chiapas highlands) and
~20 days of observations relative to today. Every seeded row has demo=1 and every name says (DEMO).

    python -m hub.seed --if-missing    # seed only if the database file does not exist yet (run.sh does this)
    python -m hub.seed --reset         # wipe everything and seed again (same as POST /api/demo/reset)

The demo story: two other members near Noor (M0123, Ondera Alto) reported ROYA in the last 7 days. When Noor
sends her own ROYA code, hers is the 3rd report within 5 km in 7 days and the outbreak alert fires.
"""
import argparse
from datetime import datetime, time, timedelta

from . import cards, db, sms

COMMUNITIES = {  # fictional names, placed in the Tseltal-speaking highlands of Chiapas
    "Ondera Alto": (16.910, -92.110),
    "Ondera Bajo": (16.870, -92.040),
    "Ondera Río": (16.965, -92.200),
    "Ondera Loma": (16.975, -92.050),
}

# member number, name, community, lat, lon, language
MEMBERS = [
    (123, "Noor", "Ondera Alto", 16.912, -92.108, "es"),
    (101, "Juana Gómez Pérez", "Ondera Alto", 16.904, -92.124, "es"),
    (105, "Pedro López Hernández", "Ondera Alto", 16.924, -92.118, "tzh"),
    (108, "Rosa Méndez Díaz", "Ondera Alto", 16.899, -92.101, "es"),
    (112, "Manuel Sántiz Gómez", "Ondera Alto", 16.917, -92.094, "tzh"),
    (116, "Lucía Hernández Sántiz", "Ondera Alto", 16.921, -92.103, "es"),
    (102, "Antonio Pérez Ruiz", "Ondera Bajo", 16.866, -92.046, "es"),
    (106, "Micaela Gómez López", "Ondera Bajo", 16.874, -92.031, "tzh"),
    (109, "Sebastián Díaz Méndez", "Ondera Bajo", 16.861, -92.038, "es"),
    (113, "Catalina Ruiz Pérez", "Ondera Bajo", 16.878, -92.049, "es"),
    (117, "Domingo Jiménez López", "Ondera Bajo", 16.869, -92.027, "es"),
    (120, "Petrona López Gómez", "Ondera Bajo", 16.857, -92.051, "tzh"),
    (103, "Andrés Sántiz Pérez", "Ondera Río", 16.962, -92.205, "es"),
    (107, "Marcela Hernández Gómez", "Ondera Río", 16.971, -92.193, "es"),
    (110, "Javier Méndez López", "Ondera Río", 16.958, -92.214, "es"),
    (114, "Pascuala Gómez Díaz", "Ondera Río", 16.976, -92.208, "tzh"),
    (118, "Alonso Pérez Jiménez", "Ondera Río", 16.953, -92.196, "es"),
    (121, "Teresa Díaz Hernández", "Ondera Río", 16.967, -92.221, "es"),
    (104, "Mariano López Méndez", "Ondera Loma", 16.972, -92.056, "es"),
    (111, "Verónica Jiménez Gómez", "Ondera Loma", 16.981, -92.044, "es"),
    (115, "Nicolás Gómez Sántiz", "Ondera Loma", 16.968, -92.039, "es"),
    (119, "Agustina Pérez López", "Ondera Loma", 16.985, -92.061, "es"),
    (122, "Francisco Hernández Ruiz", "Ondera Loma", 16.979, -92.067, "tzh"),
    (124, "Elena Méndez Pérez", "Ondera Loma", 16.962, -92.048, "es"),
]

# member number, code, conf, days ago, obs id, location ("-" = plot), how it arrived
# conf: the app (model cafetal-img-v2, threshold 0.90 in app/model/labels.json) only sends SANO/ROYA/MINA/PHOM/CERC
# with conf >= 90; DUDA carries the model's top-1 below the threshold (0 = no model run). The outbreak rule counts
# ROYA only at conf >= the threshold (hub/outbreak.py), so the two reports near Noor must be >= 90.
OBSERVATIONS = [
    # Ondera Alto: exactly two recent ROYA reports near Noor (the demo trigger needs Noor's as the 3rd)
    (105, "ROYA", 92, 2, "A1R2", (16.92, -92.12), "sms"),
    (108, "ROYA", 91, 4, "B7K4", (16.90, -92.10), "sms"),
    (101, "SANO", 91, 6, "C2M8", (16.90, -92.12), "sms"),
    (112, "MINA", 92, 9, "D5P1", "-", "sms"),
    (116, "ROYA", 93, 12, "E3T6", (16.92, -92.10), "sms"),   # too old for the 7-day window
    (123, "SANO", 96, 18, "F9N3", (16.91, -92.11), "sms"),   # Noor's earlier check
    # Ondera Bajo
    (102, "DUDA", 52, 3, "G4W7", (16.87, -92.05), "sms"),
    (106, "CERC", 92, 5, "H8Q2", (16.87, -92.03), "sms"),
    (109, "SANO", 93, 8, "J1V5", "-", "sync"),
    (113, "PHOM", 91, 14, "K6X9", (16.88, -92.05), "sms"),
    (120, "OTRO", 86, 10, "L2Z4", (16.86, -92.05), "sms"),
    # Ondera Río: one recent ROYA, alone and far away (no alert)
    (103, "ROYA", 95, 3, "M7B1", (16.96, -92.21), "sms"),
    (107, "ROYA", 90, 16, "N3C8", (16.97, -92.19), "sms"),
    (110, "MINA", 94, 6, "P5D2", (16.96, -92.21), "sms"),
    (114, "SANO", 90, 11, "Q9F6", "-", "sms"),
    (118, "DUDA", 40, 1, "R4G3", (16.95, -92.20), "sms"),
    # Ondera Loma
    (104, "SANO", 95, 2, "S8H7", (16.97, -92.06), "sms"),
    (111, "CERC", 94, 7, "T2J5", (16.98, -92.04), "sms"),
    (115, "MINA", 90, 13, "U6K1", (16.97, -92.04), "sync"),
    (119, "DUDA", 0, 5, "V1L9", "-", "sms"),
    (122, "SANO", 97, 19, "W5M4", (16.98, -92.07), "sms"),
]

# member number, text, days ago, intent label shown to the officer, confidence (free text forwarded to officer)
OFFICER_SMS = [
    (110, "cuando viene el ingeniero a la comunidad", 2, "hablar_con_tecnico", 0.97),
    (117, "las matas de abajo se secaron con el calor, que hago", 1, "otro", 0.41),
]


def phone_for(n: int) -> str:
    return f"+52967000{n:04d}"


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
                 at(60, 10, now), "Personal de la cooperativa (DEMO)", "v1", at(60, 10, now)))
        members = {m["member_id"]: m for m in db.rows(conn.execute("SELECT * FROM members"))}

        for n, code, conf, days, obs_id, loc, source in OBSERVATIONS:
            mid = f"M{n:04d}"
            d = (now - timedelta(days=days)).date()
            loc_txt = "-" if loc == "-" else f"{loc[0]:.2f},{loc[1]:.2f}"
            raw = f"CAF1 {mid} {code} {conf} {d.strftime('%Y%m%d')} {loc_txt} #{obs_id}"
            rec = {"member_id": mid, "obs_id": obs_id, "code": code, "conf": conf, "date": d.isoformat(),
                   "lat": None if loc == "-" else loc[0], "lon": None if loc == "-" else loc[1],
                   "received_at": at(days, 18, now),
                   "model_version": "cafetal-img-v2" if code != "DUDA" or conf else None}
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
        db.add_message(conn, "in", noor["phone"], "PRECIO", "received", member_id="M0123",
                       created_at=at(9, 19, now), demo=1)
        slots = sms.price_slots()
        card_id = "sms_precio" if slots else "sms_precio_sin_datos"
        text, lang = cards.render(card_id, noor["language"], **(slots or {}))
        db.add_message(conn, "out", noor["phone"], text, "sent_simulated", member_id="M0123", card_id=card_id,
                       lang=lang, created_at=at(9, 19, now), demo=1)

        for n, body, days, intent_name, conf in OFFICER_SMS:
            mid = f"M{n:04d}"
            m = members[mid]
            msg_id = db.add_message(conn, "in", m["phone"], body, "received", member_id=mid,
                                    created_at=at(days, 7, now), demo=1)
            text, lang = cards.render("sms_pasar_tecnico", m["language"])
            db.add_message(conn, "out", m["phone"], text, "sent_simulated", member_id=mid,
                           card_id="sms_pasar_tecnico", lang=lang, created_at=at(days, 7, now), demo=1)
            conn.execute(
                "INSERT INTO officer_messages(message_id, member_id, phone, body, intent, conf, created_at, demo)"
                " VALUES (?,?,?,?,?,?,?,1)", (msg_id, mid, m["phone"], body, intent_name, conf, at(days, 7, now)))
    return {"members": len(MEMBERS), "observations": len(OBSERVATIONS), "officer_messages": len(OFFICER_SMS)}


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

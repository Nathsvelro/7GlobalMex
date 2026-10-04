"""Observation SMS code v1 (PLAN.md section 5)."""
from datetime import date, timedelta

import pytest

from hub.sms import CODES, ParseError, normalize_phone, parse_code
from conftest import ymd


def test_valid_code():
    r = parse_code(f"CAF1 M0123 RUST 99 {ymd()} -0.52,37.32 #K3F9")
    assert r == {"member_id": "M0123", "code": "RUST", "conf": 99, "date": date.today().isoformat(),
                 "lat": -0.52, "lon": 37.32, "obs_id": "K3F9"}


def test_all_english_result_codes():
    assert CODES == ["HLTH", "RUST", "MINR", "PHOM", "CERC", "MITE", "OTHR", "UNSR"]
    for code in CODES:
        assert parse_code(f"CAF1 M0123 {code} 91 {ymd()} -0.52,37.32 #C0DE")["code"] == code


def test_case_and_spacing_tolerant():
    r = parse_code(f"  caf1   m0123  rust  87   {ymd()}  -0.52 , 37.32   #k3f9  ")
    assert (r["member_id"], r["code"], r["obs_id"], r["lat"], r["lon"]) == ("M0123", "RUST", "K3F9", -0.52, 37.32)


def test_location_rounded_to_two_decimals_for_privacy():
    r = parse_code(f"CAF1 M0123 HLTH 90 {ymd()} -0.51834,37.32789 #AAAA")
    assert (r["lat"], r["lon"]) == (-0.52, 37.33)


def test_unknown_location_dash():
    r = parse_code(f"CAF1 M0123 UNSR 0 {ymd()} - #ZZ01")
    assert r["lat"] is None and r["lon"] is None and r["code"] == "UNSR" and r["conf"] == 0


def test_obs_id_optional_and_one_decimal_location():
    r = parse_code(f"CAF1 M0123 RUST 87 {ymd()} -0.5,37.3")
    assert r["obs_id"] is None and r["lat"] == -0.5 and r["lon"] == 37.3


@pytest.mark.parametrize("body", [
    "CAF1 M0123 XXXX 87 {d} -0.52,37.32 #K3F9",       # unknown result code
    "CAF1 M0123 ROYA 87 {d} -0.52,37.32 #K3F9",       # old Spanish code (never deployed)
    "CAF1 M0123 DUDA 87 {d} -0.52,37.32 #K3F9",       # old Spanish fail-safe code
    "CAF1 M0123 RUST 187 {d} -0.52,37.32 #K3F9",      # confidence > 100
    "CAF1 M0123 RUST 87 20261340 -0.52,37.32 #K3F9",  # month 13
    "CAF1 M0123 RUST 87 20260230 -0.52,37.32 #K3F9",  # 30 February
    "CAF1 M0123 RUST 87 {d} -96.52,37.32 #K3F9",      # latitude out of range
    "CAF1 M123 RUST 87 {d} -0.52,37.32 #K3F9",        # member id needs 4 digits
    "CAF1 M0123 RUST 87 {d}",                         # location missing
    "CAF1 M0123 RUST 87 {d} -0.52,37.32 #K3F9 hello", # trailing text
    "CAF2 M0123 RUST 87 {d} -0.52,37.32 #K3F9",       # other version
    "CAF1 M0123 RUST 87 {d} -0.52,37.32 #K3F",        # obs id must be 4 chars
    "",
])
def test_invalid_codes(body):
    with pytest.raises(ParseError):
        parse_code(body.format(d=ymd()))


def test_date_too_far_in_future_or_past():
    future = (date.today() + timedelta(days=5)).strftime("%Y%m%d")
    old = (date.today() - timedelta(days=400)).strftime("%Y%m%d")
    for d in (future, old):
        with pytest.raises(ParseError):
            parse_code(f"CAF1 M0123 RUST 87 {d} -0.52,37.32 #K3F9")


def test_code_fits_one_sms():
    body = f"CAF1 M0123 UNSR 87 {ymd()} -89.99,-179.99 #K3F9"    # longest possible location
    assert len(body) <= 160
    parse_code(body)


def test_normalize_phone():
    assert normalize_phone("+254 700 000 123") == "+254700000123"
    assert normalize_phone("0700 000 123") == "+254700000123"      # Kenyan national format
    assert normalize_phone("0700-000-123") == "+254700000123"
    assert normalize_phone("254700000123") == "+254700000123"
    assert normalize_phone("700000123") == "+254700000123"         # without the leading 0
    assert normalize_phone("0110 000 123") == "+254110000123"      # 01xx mobile range
    assert normalize_phone("") == ""

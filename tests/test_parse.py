"""Observation SMS code v1 (PLAN.md section 5)."""
from datetime import date, timedelta

import pytest

from hub.sms import ParseError, normalize_phone, parse_code
from conftest import ymd


def test_valid_code():
    r = parse_code(f"CAF1 M0123 ROYA 87 {ymd()} 16.91,-92.11 #K3F9")
    assert r == {"member_id": "M0123", "code": "ROYA", "conf": 87, "date": date.today().isoformat(),
                 "lat": 16.91, "lon": -92.11, "obs_id": "K3F9"}


def test_case_and_spacing_tolerant():
    r = parse_code(f"  caf1   m0123  roya  87   {ymd()}  16.91 , -92.11   #k3f9  ")
    assert (r["member_id"], r["code"], r["obs_id"], r["lat"], r["lon"]) == ("M0123", "ROYA", "K3F9", 16.91, -92.11)


def test_location_rounded_to_two_decimals_for_privacy():
    r = parse_code(f"CAF1 M0123 SANO 90 {ymd()} 16.91234,-92.11789 #AAAA")
    assert (r["lat"], r["lon"]) == (16.91, -92.12)


def test_unknown_location_dash():
    r = parse_code(f"CAF1 M0123 DUDA 0 {ymd()} - #ZZ01")
    assert r["lat"] is None and r["lon"] is None and r["code"] == "DUDA" and r["conf"] == 0


def test_obs_id_optional_and_one_decimal_location():
    r = parse_code(f"CAF1 M0123 ROYA 87 {ymd()} 16.7,-92.6")
    assert r["obs_id"] is None and r["lat"] == 16.7


@pytest.mark.parametrize("body", [
    "CAF1 M0123 XXXX 87 {d} 16.91,-92.11 #K3F9",       # unknown result code
    "CAF1 M0123 ROYA 187 {d} 16.91,-92.11 #K3F9",      # confidence > 100
    "CAF1 M0123 ROYA 87 20261340 16.91,-92.11 #K3F9",  # month 13
    "CAF1 M0123 ROYA 87 20260230 16.91,-92.11 #K3F9",  # 30 February
    "CAF1 M0123 ROYA 87 {d} 96.91,-92.11 #K3F9",       # latitude out of range
    "CAF1 M123 ROYA 87 {d} 16.91,-92.11 #K3F9",        # member id needs 4 digits
    "CAF1 M0123 ROYA 87 {d}",                          # location missing
    "CAF1 M0123 ROYA 87 {d} 16.91,-92.11 #K3F9 hola",  # trailing text
    "CAF2 M0123 ROYA 87 {d} 16.91,-92.11 #K3F9",       # other version
    "CAF1 M0123 ROYA 87 {d} 16.91,-92.11 #K3F",        # obs id must be 4 chars
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
            parse_code(f"CAF1 M0123 ROYA 87 {d} 16.91,-92.11 #K3F9")


def test_code_fits_one_sms():
    body = f"CAF1 M0123 ROYA 87 {ymd()} -16.91,-92.11 #K3F9"
    assert len(body) <= 160
    parse_code(body)


def test_normalize_phone():
    assert normalize_phone("+52 967 000 0123") == "+529670000123"
    assert normalize_phone("9670000123") == "+529670000123"
    assert normalize_phone("529670000123") == "+529670000123"

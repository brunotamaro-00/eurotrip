#!/usr/bin/env python3
"""
Extrae precios Hostelworld PWA (EN) para 7 huéspedes, 2026-09-04 → 2026-09-09.
Salida JSON en stdout. Requiere: pip install playwright && playwright install chromium
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
LINKS = ROOT / "hostelworld_links.txt"


def parse_eur(s: str) -> float:
    s = s.replace("€", "").strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return 0.0
    # 86.24 (EN) | 86,24 (EU) | 1.234,56 (EU miles)
    if s.count(",") == 1 and s.count(".") == 0:
        return float(s.replace(",", "."))
    if s.count(".") == 1 and s.count(",") == 0:
        return float(s)
    if s.count(",") == 1 and s.count(".") >= 1:
        return float(s.replace(".", "").replace(",", "."))
    return float(s.replace(",", "."))


def extract_room_section(body: str) -> str:
    for marker in ("Choose your room", "Elige tu habitación"):
        i = body.find(marker)
        if i >= 0:
            end = body.find("House Rules", i)
            if end < 0:
                end = body.find("Reglas de la casa", i)
            if end < 0:
                end = i + 25000
            return body[i:end]
    return ""


def _is_room_title(ln: str, title_re: re.Pattern[str]) -> bool:
    if not ln or ln in ("Private Rooms", "Dorm Beds", "Dorm beds"):
        return False
    if title_re.search(ln):
        return True
    if re.match(r"^\d+\s*Bed\b", ln, re.I):
        return True
    if re.match(r"^(Deluxe|Twin|Premium|Classic)\s+", ln, re.I) and (
        "Room" in ln or "Bed" in ln
    ):
        return True
    return False


def parse_pricing(section: str) -> dict:
    """Parse Hostelworld PWA 'Choose your room' plain text (EN)."""
    lines = [ln.strip() for ln in section.splitlines()]
    current_name: str | None = None
    mode: str | None = None
    buf: list[float] = []
    rooms: list[dict] = []

    def save_room():
        nonlocal current_name, mode, buf
        if current_name and mode and len(buf) >= 2:
            rooms.append({"name": current_name, "mode": mode, "prices": buf[:]})
        buf = []

    title_re = re.compile(
        r"^(Standard|Superior|Deluxe|Basic|Classic|Economy|Premium)\b.+\bBed\b",
        re.I,
    )

    i = 0
    while i < len(lines):
        ln = lines[i]
        if _is_room_title(ln, title_re):
            save_room()
            current_name = ln
            mode = None
            i += 1
            continue
        if ln in ("Private Rooms", "Dorm Beds", "Dorm beds"):
            save_room()
            i += 1
            continue
        if ln.startswith("Prices are per bed") or "per cama" in ln.lower():
            save_room()
            mode = "bed"
            buf = []
            i += 1
            continue
        if ln.startswith("Prices are per room") or "por habitación" in ln.lower():
            save_room()
            mode = "room"
            buf = []
            i += 1
            continue
        m = re.match(r"€\s*([\d.,]+)", ln)
        if m and mode:
            if (
                i + 2 < len(lines)
                and lines[i + 1] == "-10%"
                and re.match(r"€\s*([\d.,]+)", lines[i + 2])
            ):
                m2 = re.match(r"€\s*([\d.,]+)", lines[i + 2])
                if m2:
                    buf.append(parse_eur(m2.group(1)))
                    i += 3
                    continue
            buf.append(parse_eur(m.group(1)))
            i += 1
            continue
        i += 1

    save_room()

    def is_8plus_dorm(name: str) -> bool:
        n = name.lower()
        if "dorm" not in n:
            return False
        m = re.search(r"(\d+)\s*bed", n, re.I)
        return bool(m and int(m.group(1)) >= 8)

    def is_6bed_dorm(name: str) -> bool:
        return "dorm" in name.lower() and bool(re.search(r"6\s*bed", name, re.I))

    def is_private_8(name: str) -> bool:
        n = name.lower()
        return "private" in n and bool(re.search(r"8\s*bed", n, re.I))

    def is_private_10(name: str) -> bool:
        n = name.lower()
        return "private" in n and bool(re.search(r"10\s*bed", n, re.I))

    def fc_nr(pr: list[float]) -> tuple[float, float] | None:
        if len(pr) >= 4:
            return pr[0], pr[2]
        if len(pr) >= 2:
            return pr[0], pr[1]
        return None

    dorm8_fc: list[float] = []
    dorm8_nr: list[float] = []
    dorm6_fc: list[float] = []
    priv8_fc: list[float] = []
    priv8_nr: list[float] = []
    priv10_fc: list[float] = []

    for r in rooms:
        name = r["name"]
        pr = r["prices"]
        pair = fc_nr(pr)
        if not pair:
            continue
        fc, nr = pair
        if r["mode"] == "bed":
            if is_8plus_dorm(name):
                dorm8_fc.append(fc * 7)
                dorm8_nr.append(nr * 7)
            if is_6bed_dorm(name):
                dorm6_fc.append(fc * 6)
        elif r["mode"] == "room":
            if is_private_8(name):
                priv8_fc.append(fc)
                priv8_nr.append(nr)
            if is_private_10(name):
                priv10_fc.append(fc)

    return {
        "rooms_parsed": len(rooms),
        "dorm8_fc_total_7": min(dorm8_fc) if dorm8_fc else None,
        "dorm8_nr_total_7": min(dorm8_nr) if dorm8_nr else None,
        "dorm6_fc_total_6": min(dorm6_fc) if dorm6_fc else None,
        "private8_fc_room": min(priv8_fc) if priv8_fc else None,
        "private8_nr_room": min(priv8_nr) if priv8_nr else None,
        "private10_fc_room": min(priv10_fc) if priv10_fc else None,
    }


def scrape_one(page, slug: str, pid: str) -> dict:
    url = (
        f"https://www.hostelworld.com/pwa/hosteldetails.php/"
        f"{slug}/Paris/{pid}?from=2026-09-04&to=2026-09-09&guests=7"
    )
    out: dict = {"propertyId": pid, "slug": slug, "url": url, "ok": False}
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=75000)
        page.wait_for_timeout(3500)
        try:
            if page.get_by_text("ARS", exact=True).first.is_visible(timeout=2500):
                page.get_by_text("ARS", exact=True).first.click()
                page.wait_for_timeout(600)
                page.get_by_text("Euro", exact=False).first.click(timeout=4000)
                page.wait_for_timeout(6000)
        except Exception:
            pass
        page.keyboard.press("End")
        page.wait_for_timeout(2500)
        body = page.evaluate("() => document.body.innerText")
        if "Sold out" in body or "Agotado" in body or "no availability" in body.lower():
            out["note"] = "posible agotado / sin habitaciones en UI"
        section = extract_room_section(body)
        if not section:
            out["error"] = "no_section"
            out["ok"] = False
            return out
        parsed = parse_pricing(section)
        out.update(parsed)
        out["ok"] = True
    except Exception as e:
        out["error"] = str(e)[:200]
    return out


def main() -> None:
    rows = []
    for raw in LINKS.read_text().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = re.search(r"hosteldetails\.php/([^/]+)/Paris/(\d+)", raw)
        if not m:
            continue
        rows.append((m.group(1), m.group(2)))

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-GB")
        for slug, pid in rows:
            r = scrape_one(page, slug, pid)
            results.append(r)
            time.sleep(1.2)
        browser.close()

    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

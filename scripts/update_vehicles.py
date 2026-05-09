#!/usr/bin/env python3
"""Daily EV database updater using openai/gpt-oss-120b:free via OpenRouter.

Also fetches real car photos from Wikipedia for any vehicle with a blank image_url.
"""

import json
import os
import re
import sys
import time
import requests
from datetime import datetime, timezone

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
VEHICLES_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "vehicles.json")

MODEL = "openai/gpt-oss-120b:free"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_UA = "EVShowcase/1.0 (github.com/richardawe/electric-vehicles)"

# Explicit Wikipedia article title per vehicle ID.
# This avoids unreliable search and guarantees we get the right image.
ARTICLE_MAP = {
    "tesla-model-3-2024":           "Tesla Model 3",
    "tesla-model-s-plaid-2024":     "Tesla Model S",
    "lucid-air-grand-touring-2024": "Lucid Air",
    "bmw-i4-m50-2024":              "BMW i4",
    "polestar-2-2024":              "Polestar 2",
    "audi-etron-gt-2024":           "Audi e-tron GT",
    "porsche-taycan-2024":          "Porsche Taycan",
    "mercedes-eqs-450-2024":        "Mercedes-Benz EQS",
    "hyundai-ioniq6-2024":          "Hyundai Ioniq 6",
    "byd-han-ev-2024":              "BYD Han",
    "nio-et7-2024":                 "NIO ET7",
    "xpeng-p7-2024":                "Xpeng P7",
    "tesla-model-y-2024":           "Tesla Model Y",
    "tesla-model-x-plaid-2024":     "Tesla Model X",
    "rivian-r1s-2024":              "Rivian R1S",
    "ford-mustang-mach-e-2024":     "Ford Mustang Mach-E",
    "hyundai-ioniq5-2024":          "Hyundai Ioniq 5",
    "kia-ev6-gt-2024":              "Kia EV6",
    "volkswagen-id4-2024":          "Volkswagen ID.4",
    "bmw-ix-xdrive50-2024":         "BMW iX",
    "audi-q8-etron-2024":           "Audi Q8 e-tron",
    "cadillac-lyriq-2024":          "Cadillac Lyriq",
    "volvo-ex90-2024":              "Volvo EX90",
    "byd-atto3-2024":               "BYD Atto 3",
    "tesla-cybertruck-awd-2024":    "Tesla Cybertruck",
    "rivian-r1t-2024":              "Rivian R1T",
    "ford-f150-lightning-2024":     "Ford F-150 Lightning",
    "gmc-hummer-ev-2024":           "GMC Hummer EV",
    "chevy-silverado-ev-2024":      "Chevrolet Silverado EV",
    "porsche-taycan-turbo-gt-2024": "Porsche Taycan",
    "rimac-nevera-2024":            "Rimac Nevera",
    "lotus-eletre-r-2024":          "Lotus Eletre",
    "tesla-roadster-2025":          "Tesla Roadster (second generation)",
    "aspark-owl-2024":              "Aspark Owl",
    "pininfarina-battista-2024":    "Automobili Pininfarina Battista",
    "zero-srf-2024":                "Zero Motorcycles",
    "harley-livewire-one-2024":     "LiveWire (motorcycle brand)",
    "energica-experia-2024":        "Energica Motor Company",
    "lightning-ls218-2024":         "Lightning Motorcycles",
    "super-soco-tc-max-2024":       "Super Soco",
    "volkswagen-id-buzz-2024":      "Volkswagen ID. Buzz",
    "mercedes-esprinter-2024":      "Mercedes-Benz eSprinter",
    "ford-e-transit-2024":          "Ford E-Transit",
    "byd-t3-2024":                  "BYD T3",
    "rivian-edv700-2024":           "Rivian EDV",
    "byd-k9-2024":                  "BYD eBus-12",
    "yutong-e12-2024":              "Yutong",
    "proterra-catalyst-e2-2024":    "Proterra",
    "new-flyer-xcelsior-xt-2024":   "New Flyer Xcelsior",
    "byd-c9-2024":                  "BYD C9",
    "kia-ev9-2024":                 "Kia EV9",
    "nissan-ariya-2024":            "Nissan Ariya",
    "toyota-bz4x-2024":             "Toyota bZ4X",
    "fisker-ocean-2024":            "Fisker Ocean",
    "chevrolet-bolt-euv-2024":      "Chevrolet Bolt EUV",
    "bmw-ix1-2024":                 "BMW iX1",
    "mercedes-eqe-2024":            "Mercedes-Benz EQE",
    "byd-dolphin-2024":             "BYD Dolphin",
    "renault-megane-e-tech-2024":   "Renault Mégane E-Tech",
}

VALID_TYPES = {"sedan", "suv", "truck", "sports", "motorcycle", "van", "bus", "commercial"}


# ── File I/O ───────────────────────────────────────────────────────────

def load_vehicles():
    with open(VEHICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_vehicles(data):
    with open(VEHICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Wikipedia image fetching ───────────────────────────────────────────

def fetch_image_by_article(article_title):
    """Fetch main image via Wikipedia REST API (no search needed, very reliable)."""
    import urllib.parse
    slug = urllib.parse.quote(article_title.replace(" ", "_"), safe="")
    try:
        resp = requests.get(
            f"{WIKIPEDIA_REST}/{slug}",
            headers={"User-Agent": WIKIPEDIA_UA},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            src = data.get("thumbnail", {}).get("source", "")
            if src:
                # Upgrade thumbnail width from default (320) to 640
                return re.sub(r"/\d+px-", "/640px-", src)
    except Exception:
        pass
    return ""


def fetch_image_by_search(make, model):
    """Fallback: search Wikipedia and return the first relevant article's image."""
    make_words = make.replace("-", " ").lower().split()
    model_words = [w for w in model.lower().split() if len(w) > 2]
    try:
        resp = requests.get(WIKIPEDIA_API, params={
            "action": "query", "list": "search",
            "srsearch": f"{make} {model}", "srlimit": 5, "format": "json",
        }, headers={"User-Agent": WIKIPEDIA_UA}, timeout=10)
        results = resp.json()["query"]["search"]
    except Exception:
        return ""

    for result in results[:5]:
        title = result["title"].lower()
        if not any(w in title for w in make_words) and not any(w in title for w in model_words):
            continue
        url = fetch_image_by_article(result["title"])
        if url:
            return url
    return ""


def populate_images(vehicles):
    """Fill image_url for every vehicle that currently has none."""
    missing = [v for v in vehicles if not v.get("image_url")]
    if not missing:
        print("All vehicles already have images.")
        return 0

    print(f"Fetching Wikipedia images for {len(missing)} vehicle(s)…")
    filled = 0
    for v in missing:
        vid = v["id"]
        # 1. Try hardcoded article title (guaranteed correct article)
        article = ARTICLE_MAP.get(vid)
        url = fetch_image_by_article(article) if article else ""
        # 2. Fall back to search for new/unknown vehicles
        if not url:
            url = fetch_image_by_search(v["make"], v["model"])
        if url:
            v["image_url"] = url
            filled += 1
            print(f"  ✓ {v['make']} {v['model']}")
        else:
            print(f"  – {v['make']} {v['model']} (no image found)")
        time.sleep(0.3)

    print(f"Images filled: {filled}/{len(missing)}")
    return filled


# ── OpenRouter LLM call ────────────────────────────────────────────────

def extract_json(text):
    """Return the first JSON object found in text, even if wrapped in prose."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start: i + 1])
                    except json.JSONDecodeError:
                        break
    raise ValueError("No valid JSON object found in response")


def call_openrouter(prompt):
    """Call openai/gpt-oss-120b:free via OpenRouter."""
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/richardawe/electric-vehicles",
        "X-Title": "EV Showcase Updater",
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }

    for attempt in range(3):
        try:
            resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=120)
        except requests.exceptions.Timeout:
            print(f"  Timeout (attempt {attempt + 1}/3)")
            continue

        if resp.status_code == 200:
            try:
                content = resp.json()["choices"][0]["message"]["content"]
                return extract_json(content)
            except (KeyError, IndexError, ValueError) as e:
                print(f"  Failed to parse response: {e}")
                sys.exit(1)

        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"  Rate limited — waiting {wait}s…")
            time.sleep(wait)
            continue

        print(f"  API error ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    print("Request failed after 3 attempts.")
    sys.exit(1)


# ── Validation ─────────────────────────────────────────────────────────

def validate_vehicle(v):
    required = ["id", "make", "model", "year", "type", "range_mi", "battery_kwh"]
    for field in required:
        if field not in v or v[field] is None:
            return False, f"missing required field: {field}"
    if v["type"] not in VALID_TYPES:
        return False, f"invalid type: {v['type']}"
    if not isinstance(v["range_mi"], (int, float)) or v["range_mi"] <= 0:
        return False, "invalid range_mi"
    if not isinstance(v["battery_kwh"], (int, float)) or v["battery_kwh"] <= 0:
        return False, "invalid battery_kwh"
    if not isinstance(v["year"], int) or not (2010 <= v["year"] <= 2030):
        return False, "invalid year"
    return True, "ok"


# ── Prompt ─────────────────────────────────────────────────────────────

def build_prompt(current_vehicles):
    summary = "\n".join(
        f"- {v['year']} {v['make']} {v['model']} ({v.get('variant', '')}) [{v['type']}]"
        for v in sorted(current_vehicles, key=lambda x: (x["make"], x["model"]))
    )

    return f"""You are an electric vehicle expert with up-to-date knowledge of all commercially available and announced EVs worldwide.

The current EV database has {len(current_vehicles)} vehicles listed below:

{summary}

Your task: Identify up to 10 electric vehicles NOT already in the database. Include vehicles from any country (USA, China, Europe, South Korea, Japan, etc.) and all categories: sedans, SUVs, trucks, sports cars, motorcycles, vans, buses, commercial vehicles.

Return ONLY a valid JSON object — no markdown, no explanation, just the JSON:
{{
  "new_vehicles": [
    {{
      "id": "make-model-year",
      "make": "Manufacturer",
      "model": "Model Name",
      "year": 2024,
      "type": "sedan|suv|truck|sports|motorcycle|van|bus|commercial",
      "variant": "Specific trim or null",
      "range_mi": 300,
      "range_km": 483,
      "battery_kwh": 82.0,
      "acceleration_0_60_sec": 4.2,
      "top_speed_mph": 145,
      "top_speed_kmh": 233,
      "dc_fast_charge_kw": 250,
      "charge_time_10_80_min": 25,
      "price_usd": 42990,
      "country": "USA",
      "global_availability": true,
      "image_url": "",
      "description": "One or two sentence description."
    }}
  ]
}}

Rules:
- Only include vehicles with confirmed, publicly available specifications
- Use null for any spec that is genuinely unknown
- Set image_url to "" (empty string) — images are fetched separately
- IDs must be lowercase with hyphens, e.g. "byd-seagull-2024"
- Do not duplicate any vehicle already listed above
- Return "new_vehicles": [] if no new vehicles can be reliably added
"""


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print(f"Loading vehicles from {VEHICLES_FILE}")
    data = load_vehicles()
    current_vehicles = data.get("vehicles", [])
    existing_ids = {v["id"] for v in current_vehicles}

    print(f"Current database: {len(current_vehicles)} vehicles")

    # Step 1: ask the LLM for new vehicles
    print(f"Calling OpenRouter API (model: {MODEL})…")
    prompt = build_prompt(current_vehicles)
    result = call_openrouter(prompt)

    new_vehicles = result.get("new_vehicles", [])
    print(f"Model returned {len(new_vehicles)} candidate vehicle(s)")

    added = 0
    for vehicle in new_vehicles:
        vid = vehicle.get("id", "unknown")
        if vid in existing_ids:
            print(f"  Skip (duplicate): {vid}")
            continue
        ok, reason = validate_vehicle(vehicle)
        if not ok:
            print(f"  Skip (invalid — {reason}): {vid}")
            continue
        vehicle.setdefault("image_url", "")
        current_vehicles.append(vehicle)
        existing_ids.add(vid)
        added += 1
        print(f"  Added: {vehicle['year']} {vehicle['make']} {vehicle['model']}")

    # Step 2: fill in missing images from Wikipedia
    print()
    images_filled = populate_images(current_vehicles)

    # Step 3: save
    data["vehicles"] = current_vehicles
    data["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data["vehicle_count"] = len(current_vehicles)
    save_vehicles(data)

    print(f"\nDone. Added {added} vehicle(s), filled {images_filled} image(s). Total: {len(current_vehicles)}")


if __name__ == "__main__":
    main()

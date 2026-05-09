#!/usr/bin/env python3
"""Daily EV database updater using openai/gpt-oss-120b:free via OpenRouter.

Also fetches real car photos from Wikipedia for any vehicle with a blank image_url.
"""

import json
import os
import re
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
    "zero-srf-2024":                "Zero SR/F",
    "harley-livewire-one-2024":     "LiveWire One",
    "energica-experia-2024":        "Energica Experia",
    "lightning-ls218-2024":         "Lightning LS-218",
    "super-soco-tc-max-2024":       "Super Soco TC Max",
    "volkswagen-id-buzz-2024":      "Volkswagen ID. Buzz",
    "mercedes-esprinter-2024":      "Mercedes-Benz eSprinter",
    "ford-e-transit-2024":          "Ford E-Transit",
    "byd-t3-2024":                  "BYD T3",
    "rivian-edv700-2024":           "Rivian EDV",
    "byd-k9-2024":                  "BYD K9",
    "yutong-e12-2024":              "Yutong E12",
    "proterra-catalyst-e2-2024":    "Proterra Catalyst",
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
    # Round 2 additions
    "bmw-i5-2024":                  "BMW i5",
    "mercedes-eqb-2024":            "Mercedes-Benz EQB",
    "volkswagen-id7-2024":          "Volkswagen ID.7",
    "ford-explorer-ev-2024":        "Ford Explorer EV",
    "tesla-semi-2024":              "Tesla Semi",
    "rivian-r2-2024":               "Rivian R2",
    "byd-seal-2024":                "BYD Seal",
    "lucid-gravity-2024":           "Lucid Gravity",
    "kia-ev8-2024":                 "Kia EV8",
    "bmw-i7-2024":                  "BMW i7",
    "mercedes-eqe-suv-2024":        "Mercedes-Benz EQE SUV",
    "volkswagen-id5-2024":          "Volkswagen ID.5",
    "honda-e-2024":                 "Honda e",
    "nissan-leaf-2024":             "Nissan Leaf",
    "polestar-4-2024":              "Polestar 4",
    "kia-ev5-2024":                 "Kia EV5",
    "volvo-fl-electric-2024":       "Volvo FL",
    "proterra-zx5-2024":            "Proterra ZX5",
    "fisker-pear-2025":             "Fisker PEAR",
    # LLM-added vehicles (Round 3+)
    "hyundai-ioniq-7-2024":         "Hyundai Ioniq 7",
    "kia-ev7-2024":                 "Kia EV7",
    "mazda-mx-30-2024":             "Mazda MX-30",
    "honda-prologue-2024":          "Honda Prologue",
    "nissan-z-ev-2024":             "Nissan Z",
    "bmw-ix2-2024":                 "BMW iX2",
    "volkswagen-id-2-2024":         "Volkswagen ID.2",
    "leapmotor-c11-2024":           "Leapmotor C11",
    # LLM-added vehicles (Round 4+)
    "skoda-enyaq-iv-2024":          "Škoda Enyaq",
    "peugeot-e-208-2024":           "Peugeot e-208",
    "opel-corsa-e-2024":            "Opel Corsa-e",
    "kia-ev6-standard-2024":        "Kia EV6",
    "porsche-macan-ev-2024":        "Porsche Macan (electric)",
    "genesis-gv60-2024":            "Genesis GV60",
    "genesis-g80-electrified-2024": "Genesis G80",
    "subaru-solterra-2024":         "Subaru Solterra",
    "freightliner-ecascadia-2024":  "Freightliner eCascadia",
    "volvo-vnr-electric-2024":      "Volvo VNR Electric",
    "energica-eva-ribelle-2024":    "Energica Eva Ribelle",
    "peugeot-e-2008-2024":          "Peugeot e-2008",
    "renault-zoe-2024":             "Renault Zoé",
    "nova-bus-lfse-2024":           "Nova Bus LFSe",
    "ford-f-150-lightning-2025":    "Ford F-150 Lightning",
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
    """Fetch main image for a Wikipedia article title.

    Tries two Wikipedia APIs in sequence:
      1. REST summary endpoint (fast, returns thumbnail directly)
      2. MediaWiki pageimages API (more reliable for articles where REST lacks thumbnail)
    """
    import urllib.parse
    slug = urllib.parse.quote(article_title.replace(" ", "_"), safe="-._~")
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
                return re.sub(r"/\d+px-", "/640px-", src)
    except Exception:
        pass

    # Fallback: MediaWiki pageimages API — works when REST summary lacks thumbnail
    try:
        resp2 = requests.get(WIKIPEDIA_API, params={
            "action": "query", "titles": article_title,
            "prop": "pageimages", "pithumbsize": 640,
            "format": "json",
        }, headers={"User-Agent": WIKIPEDIA_UA}, timeout=10)
        if resp2.status_code == 200:
            pages = resp2.json().get("query", {}).get("pages", {})
            for page in pages.values():
                src = page.get("thumbnail", {}).get("source", "")
                if src:
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


def _commons_query(query, make_words):
    """Run one Wikimedia Commons file-namespace search and return the best image URL."""
    try:
        resp = requests.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",   # File: namespace only
            "gsrlimit": "10",
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": "640",
            "format": "json",
        }, headers={"User-Agent": WIKIPEDIA_UA}, timeout=15)
        pages = resp.json().get("query", {}).get("pages", {})
    except Exception:
        return ""

    def score(page):
        title = page.get("title", "").lower()
        if title.endswith(".svg") or any(w in title for w in ("logo", "icon", "map", "diagram", "flag", "badge")):
            return 0
        bonus = 2 if any(w in title for w in make_words) else 0
        return 1 + bonus

    ranked = sorted(pages.values(), key=lambda p: (-score(p), p.get("index", 99)))
    for page in ranked:
        if score(page) == 0:
            continue
        info = page.get("imageinfo", [{}])[0]
        thumb = info.get("thumburl", "")
        if thumb:
            return thumb
    return ""


def search_commons_image(make, model):
    """Last resort: search Wikimedia Commons file namespace directly.

    Commons has millions of free-licensed photos including vehicles with no
    Wikipedia article (new models, obscure brands, buses, motorcycles, etc.).
    All results are CC/public-domain — free and open license guaranteed.
    Tries multiple queries from specific to broad to maximise hit rate.
    """
    make_words = make.replace("-", " ").lower().split()
    queries = [
        f"{make} {model}",
        f"{make} {model} electric",
        f"{make} {model} EV",
        make,                        # last resort: brand name only
    ]
    for q in queries:
        url = _commons_query(q, make_words)
        if url:
            return url
    return ""


def populate_images(vehicles):
    """Fill image_url for every vehicle that currently has none.

    Fetch order (all sources are free/open Wikimedia license):
      1. Wikipedia REST API via ARTICLE_MAP — guaranteed correct article
      2. Wikipedia article search — for new vehicles not in the map
      3. Wikimedia Commons file search — last resort (covers anything missing)
    """
    missing = [v for v in vehicles if not v.get("image_url")]
    if not missing:
        print("All vehicles already have images.")
        return 0

    print(f"Fetching images for {len(missing)} vehicle(s)…")
    filled = 0
    for v in missing:
        vid = v["id"]
        # 1. Known article title
        article = ARTICLE_MAP.get(vid)
        url = fetch_image_by_article(article) if article else ""
        # 2. Wikipedia search
        if not url:
            url = fetch_image_by_search(v["make"], v["model"])
        # 3. Wikimedia Commons direct file search
        if not url:
            url = search_commons_image(v["make"], v["model"])
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
    """Return the first valid JSON object found in text.

    Handles reasoning models (gpt-oss-120b, DeepSeek R1, etc.) that wrap
    their chain-of-thought in <think>…</think> or similar tags before
    outputting the actual JSON payload.
    """
    # Strip chain-of-thought wrappers emitted by reasoning models
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
    text = text.strip()

    # 1. Direct parse (model returned clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. JSON inside a markdown code fence
    for pattern in (r"```json\s*(\{.*?\})\s*```", r"```\s*(\{.*?\})\s*```"):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

    # 3. Bracket-match the outermost {...}
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
    """Call openai/gpt-oss-120b:free via OpenRouter. Raises RuntimeError on failure."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY environment variable not set")

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
                raise RuntimeError(f"Failed to parse LLM response: {e}")

        if resp.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"  Rate limited — waiting {wait}s…")
            time.sleep(wait)
            continue

        raise RuntimeError(f"API error ({resp.status_code}): {resp.text[:200]}")

    raise RuntimeError("Request failed after 3 attempts")


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

    # Step 1: ask the LLM for new vehicles (non-fatal — image fill always runs)
    added = 0
    if OPENROUTER_API_KEY:
        try:
            print(f"Calling OpenRouter API (model: {MODEL})…")
            prompt = build_prompt(current_vehicles)
            result = call_openrouter(prompt)
            new_vehicles = result.get("new_vehicles", [])
            print(f"Model returned {len(new_vehicles)} candidate vehicle(s)")
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
        except RuntimeError as e:
            print(f"  LLM call failed ({e}) — skipping new vehicle discovery.")
    else:
        print("No OPENROUTER_API_KEY — skipping LLM call.")

    # Step 2: fill in missing images from Wikipedia (always runs)
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

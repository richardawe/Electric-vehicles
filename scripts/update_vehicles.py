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
WIKIPEDIA_UA = "EVShowcase/1.0 (github.com/richardawe/electric-vehicles)"

VALID_TYPES = {"sedan", "suv", "truck", "sports", "motorcycle", "van", "bus", "commercial"}


# ── File I/O ───────────────────────────────────────────────────────────

def load_vehicles():
    with open(VEHICLES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_vehicles(data):
    with open(VEHICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Wikipedia image fetching ───────────────────────────────────────────

def wikipedia_image_for_title(title):
    """Return the thumbnail URL for a Wikipedia article title, or ''."""
    try:
        resp = requests.get(WIKIPEDIA_API, params={
            "action": "query",
            "titles": title,
            "prop": "pageimages",
            "pithumbsize": 640,
            "piprop": "thumbnail",
            "format": "json",
        }, headers={"User-Agent": WIKIPEDIA_UA}, timeout=10)
        pages = resp.json()["query"]["pages"]
        for page in pages.values():
            src = page.get("thumbnail", {}).get("source", "")
            if src:
                return src
    except Exception:
        pass
    return ""


def fetch_wikipedia_image(make, model):
    """Search Wikipedia for a vehicle and return its main photo URL."""
    try:
        resp = requests.get(WIKIPEDIA_API, params={
            "action": "query",
            "list": "search",
            "srsearch": f"{make} {model} electric vehicle",
            "srlimit": 3,
            "format": "json",
        }, headers={"User-Agent": WIKIPEDIA_UA}, timeout=10)
        results = resp.json()["query"]["search"]
    except Exception:
        return ""

    for result in results[:3]:
        title = result["title"]
        title_lower = title.lower()
        # Require at least one of make/model to appear in the article title
        if make.lower() not in title_lower and model.lower() not in title_lower:
            continue
        url = wikipedia_image_for_title(title)
        if url:
            return url

    return ""


def populate_images(vehicles):
    """Fill in image_url for every vehicle that currently has none."""
    missing = [v for v in vehicles if not v.get("image_url")]
    if not missing:
        print("All vehicles already have images.")
        return 0

    print(f"Fetching Wikipedia images for {len(missing)} vehicle(s)…")
    filled = 0
    for v in missing:
        url = fetch_wikipedia_image(v["make"], v["model"])
        if url:
            v["image_url"] = url
            filled += 1
            print(f"  ✓ {v['make']} {v['model']}")
        else:
            print(f"  – {v['make']} {v['model']} (no image found)")
        time.sleep(0.5)  # respectful rate-limiting for Wikipedia

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

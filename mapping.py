#!/usr/bin/env python3
"""
Interactive Leaflet map of Armenian khachkars.

Improvements:
• Smarter geocoding: removes parentheses and tries multiple countries
• Same output: khachkars_map.html
"""

import json, html, re
from pathlib import Path

import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import folium
from folium.plugins import MarkerCluster

# ── 1.  load & flatten ─────────────────────────────────────────────────────
DATA_DIR = Path("/Users/aranbagdasarian/Downloads/Khachkar.Data-master")
records = []

for jf in sorted(DATA_DIR.glob("*.json")):
    with open(jf, encoding="utf-8") as f:
        top = json.load(f)

    place = (top.get("Place") or "").strip()
    site  = (top.get("Site")  or "").strip()

    for k in top.get("Khachkars", []):
        records.append({
            "place":       place,
            "site":        site,
            "imageurl":    (k.get("ImageUrl")    or "").strip(),
            "name":        (k.get("Name")        or "").strip(),
            "location":    (k.get("Location")    or "").strip(),
            "origin":      (k.get("Origin")      or "").strip(),
            "sculptor":    (k.get("Sculptor")    or "").strip(),
            "date":        (k.get("Date")        or "").strip(),
            "description": (k.get("Description") or "").strip(),
            "source":      (k.get("Source")      or "").strip(),
        })

df = pd.DataFrame(records)
print(f"✔ Loaded {len(df)} khachkars")

# ── 2.  geocode with clever fall‑backs ─────────────────────────────────────
# … (imports, data‑loading code unchanged) …

# ── 2.  geocode with clever fall‑backs ─────────────────────────────────────

COUNTRIES = ["Armenia", "Turkey", "Georgia", "Iran", "Azerbaijan"]

# ✦ ✦ NEW: manual fixes for locations Nominatim can’t resolve ✦ ✦
MANUAL = {
    # Haghartsin Monastery, near Dilijan, Armenia
    "Haghartzin (Dilijan)":      (40.8016, 44.8909),   # lat, lon  :contentReference[oaicite:0]{index=0}
    # Kamsarakan S. Astvatsatsin Church, Talin, Armenia
    "Talin Kamsarakan (Talin)":  (40.3874, 43.8733),   # lat, lon  :contentReference[oaicite:1]{index=1}
}

CACHE = Path("geocode_cache.csv")
cache_df = pd.read_csv(CACHE) if CACHE.exists() else pd.DataFrame(columns=["query","lat","lon"])
cache = {q: (la, lo) for q, la, lo in zip(cache_df["query"], cache_df["lat"], cache_df["lon"])}

# preload manual entries into the cache dict so they’re never queried
cache.update(MANUAL)

geocoder = Nominatim(user_agent="khachkar_mapper")
geocode  = RateLimiter(geocoder.geocode, min_delay_seconds=1.1)

def strip_parens(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", text).strip()

new_rows = []
for loc_raw in sorted(set(df["location"]) - set(cache)):
    loc_clean = strip_parens(loc_raw)
    found = None

    for ctry in COUNTRIES:
        found = geocode(f"{loc_clean}, {ctry}")
        if found:
            break

    if not found:
        found = geocode(strip_parens(loc_raw))

    if found:
        cache[loc_raw] = (found.latitude, found.longitude)
        new_rows.append({"query": loc_raw,
                         "lat": found.latitude,
                         "lon": found.longitude})
    else:
        print("⚠️  couldn’t geocode:", loc_raw)

# append only the newly fetched ones (manual entries already exist)
if new_rows:
    cache_df = pd.concat([cache_df, pd.DataFrame(new_rows)], ignore_index=True)
    cache_df.to_csv(CACHE, index=False)

# … (rest of script unchanged) …

df["lat"] = df["location"].map(lambda x: cache.get(x, (None, None))[0])
df["lon"] = df["location"].map(lambda x: cache.get(x, (None, None))[1])
df = df.dropna(subset=["lat", "lon"])
print(f"✔ Geocoded {len(df)} khachkars (cached + new)")

# ── 3.  build map ──────────────────────────────────────────────────────────
center = [df["lat"].mean(), df["lon"].mean()]
m       = folium.Map(location=center, zoom_start=7, control_scale=True)
cluster = MarkerCluster().add_to(m)

for _, row in df.iterrows():
    img_full = str(row["imageurl"])
    if not img_full:
        continue

    thumb = img_full.replace(".jpg", "-thumb.jpg")  # tweak if thumbs differ
    popup_html = f"""
      <div style='width:240px'>
        <a href="{html.escape(img_full)}" target="_blank">
          <img src="{html.escape(thumb)}" style="width:100%; border-radius:6px">
        </a><br>
        <b>{html.escape(row['name'] or 'Khachkar')}</b><br>
        <i>{html.escape(row['location'] or row['place'])}</i><br>
        Date: {html.escape(row['date'] or '—')}<br>
        Sculptor: {html.escape(row['sculptor'] or '—')}<br>
        {html.escape(row['description'])}
      </div>
    """

    folium.Marker(
        location=[row["lat"], row["lon"]],
        tooltip=f"{row['name'] or 'Khachkar'} – {row['location']}",
        popup=folium.Popup(popup_html, max_width=260),
        icon=folium.Icon(color="darkpurple", icon="cross", prefix="fa"),
    ).add_to(cluster)

OUTPUT = "khachkars_map.html"
m.save(OUTPUT)
print(f"✅ Map saved to {OUTPUT}")

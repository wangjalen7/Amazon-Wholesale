#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
import json

def scrape_amazon(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = year = color = price = None

    # 1) HTML title
    if t := soup.find(id="productTitle"):
        title = t.get_text(strip=True)

    # 2) JSON-LD <script> Product
    for ld in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(ld.string)
        except (TypeError, json.JSONDecodeError):
            continue
        prod = None
        if isinstance(data, list):
            prod = next((o for o in data if o.get("@type")=="Product"), None)
        elif data.get("@type")=="Product":
            prod = data
        if not prod:
            continue

        title = title or prod.get("name")
        if offers := prod.get("offers"):
            price = price or (offers.get("price") if isinstance(offers, dict) else None)
        color = color or prod.get("color")
        if rd := prod.get("releaseDate"):
            if m := re.search(r"\b(19|20)\d{2}\b", rd):
                year = year or m.group(0)
        break

    # 3) Detail bullets
    for li in soup.select("#detailBullets_feature_div .a-list-item"):
        ps = [s.strip() for s in li.stripped_strings]
        if len(ps) < 2:
            continue
        key, val = ps[0].rstrip(":"), ps[1]
        kl = key.lower()
        if "date first available" in kl and not year:
            if m := re.search(r"\b(19|20)\d{2}\b", val):
                year = m.group(0)
        if kl.startswith("color") and not color:
            color = val

    # 4) Detail tables
    for tid in (
        "productDetails_detailBullets_sections1",
        "productDetails_techSpec_section_1",
        "productDetails_techSpec_section_2"
    ):
        tbl = soup.find("table", id=tid)
        if not tbl:
            continue
        for row in tbl.find_all("tr"):
            th, td = row.find("th"), row.find("td")
            if not th or not td:
                continue
            h, v = th.get_text(strip=True).lower(), td.get_text(strip=True)
            if ("date first available" in h or "first available" in h) and not year:
                if m := re.search(r"\b(19|20)\d{2}\b", v):
                    year = m.group(0)
            if h in ("color", "colour", "color name") and not color:
                color = v

    # 5) On-page price
    if not price:
        if off := soup.select_one("span.a-price span.a-offscreen"):
            price = off.get_text(strip=True)

    # 6) Variant widget span fallback
    if not color and (var := soup.find(id=re.compile("variation_color_name", re.I))):
        if sel := var.find("span", class_="selection"):
            txt = sel.get_text(strip=True)
            if txt:
                color = txt

    # 7) Variant widget image-alt fallback
    if not color and (img := soup.select_one("#variation_color_name img[alt]")):
        alt = img["alt"].strip()
        if alt:
            color = alt

    # 8) **NEW**: Twister JSON-init blob
    if not color and (tw := soup.find(id="twister-js-init-dpx-data")):
        try:
            tw_data = json.loads(tw.get_text())
            cn = tw_data.get("color_name", {})
            opts = cn.get("options", [])
            defval = cn.get("defaultValue")
            # find the default option
            if defval:
                for o in opts:
                    if o.get("id")==defval:
                        color = o.get("value")
                        break
            # otherwise first option
            if not color and opts:
                color = opts[0].get("value")
        except json.JSONDecodeError:
            pass

    return {
        "title": title,
        "year": year,
        "color": color,
        "price": price
    }

if __name__ == "__main__":
    url = "https://www.amazon.com/dp/B0DGJ4RTVT?language=en_US"
    print(json.dumps(scrape_amazon(url), indent=2))

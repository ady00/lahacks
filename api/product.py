"""Product links -> {url, vendor, title, price, category, image, error}.

A purchase request can be a link to the thing. The page's own metadata (JSON-LD Product, OpenGraph, or Amazon's
markup) gives the title, price and category; the model reads the title like any other description and Z3 decides.
ponytail: regex over the HTML, no parser dependency. A blocked or odd page yields no metadata plus an `error`
sentence for the person, never an exception: the check still runs on what they typed.
"""
import html as _html
import json
import re
from urllib.parse import urlparse

import httpx

VENDORS = {  # host suffix -> display name; a new store is one line here
    "amazon.com": "Amazon", "amazon.ca": "Amazon", "amazon.co.uk": "Amazon", "amzn.com": "Amazon", "a.co": "Amazon",
    "bestbuy.com": "Best Buy", "walmart.com": "Walmart", "target.com": "Target", "apple.com": "Apple",
    "newegg.com": "Newegg", "ebay.com": "eBay", "bhphotovideo.com": "B&H Photo", "homedepot.com": "Home Depot",
    "costco.com": "Costco", "staples.com": "Staples", "officedepot.com": "Office Depot", "dell.com": "Dell",
    "microcenter.com": "Micro Center", "etsy.com": "Etsy", "ikea.com": "IKEA", "wayfair.com": "Wayfair",
}
_URL = re.compile(r"https?://[^\s<>\"'()\[\]]+")
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9",
}
_LD = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
_META = r"""<meta[^>]+(?:property|name)=["']{key}["'][^>]+content=["']([^"']*)["']"""
_BLOCKED = ("robot check", "captcha", "api-services-support@amazon.com", "access denied")


def vendor_of(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return next((name for suffix, name in VENDORS.items() if host == suffix or host.endswith("." + suffix)), None)


def find(text: str) -> tuple[str, str] | None:
    """First link in the text that points at a known store -> (url, vendor)."""
    for m in _URL.finditer(text or ""):
        url = m.group(0).rstrip(".,;:!?")
        if (v := vendor_of(url)):
            return url, v
    return None


def _money(s) -> float | None:
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s) if s > 0 else None
    m = re.search(r"\d[\d,]*(?:\.\d{1,2})?", str(s or ""))
    x = float(m.group(0).replace(",", "")) if m else 0
    return x if x > 0 else None


def _meta(page: str, key: str) -> str | None:
    m = re.search(_META.format(key=re.escape(key)), page, re.I)
    return _html.unescape(m.group(1)).strip() or None if m else None


def _first(x):
    return x[0] if isinstance(x, list) and x else x


def _ld_products(page: str):
    for block in _LD.findall(page):
        try:
            stack = [json.loads(block.strip())]
        except ValueError:
            continue
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                t = x.get("@type")
                if "Product" in (t if isinstance(t, list) else [t]):
                    yield x
                stack.extend(v for k, v in x.items() if k in ("@graph", "mainEntity", "itemListElement", "item"))


def _empty(url: str) -> dict:
    return {"url": url, "vendor": vendor_of(url) or (urlparse(url).hostname or url), "title": None, "price": None,
            "category": None, "image": None, "error": None}


def parse(page: str, url: str) -> dict:
    out = _empty(url)
    for p in _ld_products(page):  # 1. schema.org Product (most big stores)
        offers = _first(p.get("offers")) or {}
        out["title"] = out["title"] or p.get("name") or None
        out["price"] = out["price"] or _money(offers.get("price") or offers.get("lowPrice"))
        out["category"] = out["category"] or (p["category"] if isinstance(p.get("category"), str) else None)
        img = _first(p.get("image"))
        out["image"] = out["image"] or (img.get("url") if isinstance(img, dict) else img if isinstance(img, str) else None)
    # 2. OpenGraph
    out["title"] = out["title"] or _meta(page, "og:title") or _meta(page, "title")
    out["price"] = out["price"] or _money(_meta(page, "product:price:amount") or _meta(page, "og:price:amount"))
    out["image"] = out["image"] or _meta(page, "og:image")
    # 3. Amazon's own markup
    if m := re.search(r'id="productTitle"[^>]*>\s*(.*?)\s*<', page, re.S):
        out["title"] = _html.unescape(m.group(1)).strip() or out["title"]
    if out["price"] is None and (m := re.search(r'class="a-offscreen">\s*\$?([\d,]+\.?\d*)\s*<', page)):
        out["price"] = _money(m.group(1))
    if out["category"] is None:
        crumbs = [_html.unescape(c).strip() for c in re.findall(r'a-link-normal a-color-tertiary"[^>]*>\s*([^<]+?)\s*<', page)]
        rank = re.search(r"#[\d,]+ in ([^(<\n]+?)\s*(?:\(|<)", page)
        out["category"] = " › ".join(c for c in crumbs[:3] if c) or (_html.unescape(rank.group(1)).strip() if rank else None)
    if out["image"] is None and (m := re.search(r'"hiRes":"(https://[^"]+)"', page)):
        out["image"] = m.group(1)
    # 4. the <title> tag, last resort, unless this is a bot wall whose title would be "Robot Check"
    blocked = out["price"] is None and any(b in page[:300000].lower() for b in _BLOCKED)
    if out["title"] is None and not blocked and (m := re.search(r"<title>\s*(.*?)\s*</title>", page, re.S)):
        out["title"] = _html.unescape(m.group(1)).strip() or None
    if out["title"]:
        out["title"] = re.sub(r"^Amazon\.com\s*:\s*", "", out["title"])[:160]
    if out["title"] is None and out["price"] is None:
        out["error"] = f"{out['vendor']} blocked the request" if blocked else "no product details on that page"
    return out


def fetch(url: str) -> dict:
    """Read one product page. Tests patch this; nothing else in the API talks to a store."""
    try:
        r = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=8.0)
    except httpx.HTTPError:
        return {**_empty(url), "error": f"could not reach {vendor_of(url) or 'the store'}"}
    if r.status_code != 200:
        return {**_empty(url), "error": f"{vendor_of(url) or 'the store'} answered {r.status_code}"}
    return parse(r.text, url)


def lookup(text: str) -> dict | None:
    f = find(text)
    return fetch(f[0]) if f else None


def describe(p: dict) -> str:
    """The sentence the model reads in place of the bare link."""
    if not p.get("title"):
        return f"A link to a product on {p['vendor']} (the page could not be read)."
    bits = [p["title"]]
    if p.get("category"):
        bits.append(f"category: {p['category']}")
    if p.get("price"):
        bits.append(f"price ${p['price']:.2f}")
    return f"Product on {p['vendor']}: " + ", ".join(bits) + "."

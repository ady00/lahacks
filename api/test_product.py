from api import product as products

AMAZON = """<html><head><title>Amazon.com: Apple iPad Air (5th Generation): with M1 chip</title></head><body>
<span id="productTitle" class="a-size-large">
        Apple iPad Air (5th Generation): with M1 chip, 64GB
       </span>
<span class="a-price"><span class="a-offscreen">$393.34</span></span>
<a class="a-link-normal a-color-tertiary" href="/x">Electronics</a>
<a class="a-link-normal a-color-tertiary" href="/y">Computers &amp; Tablets</a>
<script>var x = {"hiRes":"https://m.media-amazon.com/images/I/61lv79X8rsL._AC_SL1500_.jpg"};</script></body></html>"""
LD = """<html><head><script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"Product",
"name":"Dell 27 Monitor - S2722DC","category":"Monitors","image":["https://i.dell.com/s2722dc.jpg"],
"offers":{"@type":"Offer","price":"279.99","priceCurrency":"USD"}}]}</script></head></html>"""
OG = """<html><head><meta property="og:title" content="Logitech MX Keys Keyboard">
<meta property="product:price:amount" content="99.99"><meta property="og:image" content="https://x/y.jpg"></head></html>"""
ROBOT = "<html><head><title>Robot Check</title></head><body>api-services-support@amazon.com</body></html>"
URL = "https://www.amazon.com/dp/B09V3KXJPB"


def test_parse_amazon_markup():
    p = products.parse(AMAZON, URL)
    assert p["vendor"] == "Amazon" and p["title"].startswith("Apple iPad Air (5th Generation)")
    assert p["price"] == 393.34 and p["category"] == "Electronics › Computers & Tablets"
    assert p["image"].endswith(".jpg") and p["error"] is None


def test_parse_jsonld_and_opengraph():
    p = products.parse(LD, "https://www.dell.com/en-us/shop/monitor")
    assert (p["vendor"], p["title"], p["price"], p["category"]) == ("Dell", "Dell 27 Monitor - S2722DC", 279.99, "Monitors")
    assert p["image"] == "https://i.dell.com/s2722dc.jpg"
    p = products.parse(OG, "https://www.bestbuy.com/site/x/1.p")
    assert (p["title"], p["price"], p["image"]) == ("Logitech MX Keys Keyboard", 99.99, "https://x/y.jpg")


def test_blocked_or_empty_page_is_an_error_sentence():
    p = products.parse(ROBOT, URL)
    assert p["title"] is None and p["price"] is None and p["error"] == "Amazon blocked the request"
    assert products.parse("<html></html>", URL)["error"] == "no product details on that page"


def test_find_only_known_stores():
    assert products.find(f"iPad for demos {URL}.") == (URL, "Amazon")
    assert products.find("see https://amazon.com.evil.example/dp/x") is None
    assert products.find("see https://example.com/dp/x") is None and products.find("no link") is None
    assert products.describe({"vendor": "Amazon", "title": "iPad", "category": "Tablets", "price": 393.34}) == \
        "Product on Amazon: iPad, category: Tablets, price $393.34."


def _fake(title="Dell 27 Monitor", price=279.99, error=None):
    return lambda url: {"url": url, "vendor": "Amazon", "title": title, "price": price, "category": "Monitors",
                        "image": None, "error": error}


def test_check_with_a_product_link(client, monkeypatch):
    monkeypatch.setattr(products, "fetch", _fake())
    body = {"text": f"Monitor for my desk {URL}", "employee_id": "e_newhire"}
    c = client.post("/check", json=body).json()
    assert c["product"]["title"] == "Dell 27 Monitor" and c["product"]["url"] == URL
    assert c["facts"]["amount"] == {"value": 279.99, "source": "product", "p": None}
    assert c["text"] == body["text"]  # what the person typed is kept; the model saw the title too
    # an explicit amount wins over the page price
    c2 = client.post("/check", json={**body, "amount": 10}).json()
    assert c2["facts"]["amount"] == {"value": 10, "source": "user", "p": None}
    # re-proving keeps the product and its price
    r = client.post(f"/cases/{c['case_id']}/answer", json={"fact": "receipt_attached", "value": True}).json()
    assert r["product"]["title"] == "Dell 27 Monitor" and r["facts"]["amount"]["source"] == "product"
    assert client.post("/check", json={"text": "Lunch, $12", "employee_id": "e_newhire"}).json()["product"] is None


def test_check_with_an_unreadable_product_page(client, monkeypatch):
    monkeypatch.setattr(products, "fetch", _fake(title=None, price=None, error="Amazon blocked the request"))
    c = client.post("/check", json={"text": f"Monitor for my desk {URL}", "employee_id": "e_newhire"}).json()
    assert c["product"]["error"] == "Amazon blocked the request" and "amount" not in c["facts"]
    assert c["verdict"] == "undetermined" and any(q["fact"] == "amount" for q in c["questions"])

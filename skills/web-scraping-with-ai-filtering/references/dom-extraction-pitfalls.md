# DOM Extraction Pitfalls

Common mistakes when parsing HTML for product data. Each pitfall includes the mechanism (why it fails) and the fix.

## Price Extraction from Split Elements

**Pitfall:** Numeric values with formatting (thousands separators, currency symbols) span multiple DOM elements or text nodes, but regex stops at the first space.

**Mechanism:** A product price displays as "R 1 299" on the page, which renders as:
```html
<span class="price">
  <span class="currency">R</span>
  <span class="amount">1 299</span>
</span>
```
Or as a single text node with embedded spaces. Regex `R\s+([\d,]+)` matches "R 1" only, because `[\d,]+` stops at the first space.

**Fix:** Include spaces in the character class, then strip them:
```python
import re

price_text = "R 1 299"  # From page or element.text_content()
price_match = re.search(r'R\s+([\d\s,]+)', price_text)  # Capture spaces
if price_match:
    price_raw = price_match.group(1).strip()  # "1 299"
    price_clean = re.sub(r'\s+', '', price_raw)  # "1299" (remove all spaces)
    price = f"R {price_clean}"  # Output: "R 1299"
```

Alternatively, extract the numeric portion and reconstruct:
```python
price_digits = re.sub(r'[^\d]', '', price_text)  # "11299" — WRONG if currency has digits
```
Do NOT use the above; it's fragile. Stick with the first approach (capture with spaces, strip after).

## Relative URLs Without Domain

**Pitfall:** Product URLs or image URLs are relative (`/shop/product/123`) but Telegram/Discord/email needs absolute URLs.

**Mechanism:** HTML contains:
```html
<a href="/shop/products/ingco-drill-12345">Product</a>
<img src="/media/cache/product-12345.jpg" />
```
When you send `/media/...` to Telegram, it tries `https://telegram.org/media/...` (404). The domain is missing.

**Fix:** Always construct absolute URLs before returning:
```python
from urllib.parse import urljoin

BASE_URL = "https://www.cashconverters.co.za"  # Set once at module level

def extract_product(element):
    url = element.find('a')['href']  # "/shop/products/..."
    image_url = element.find('img')['src']  # "/media/..."
    
    # Convert to absolute
    url = urljoin(BASE_URL, url)  # "https://www.cashconverters.co.za/shop/products/..."
    image_url = urljoin(BASE_URL, image_url)  # "https://www.cashconverters.co.za/media/..."
    
    return {"url": url, "image_url": image_url}
```

## Brittle CSS Selectors

**Pitfall:** Selectors like `div.product:nth-child(1)` or `article:nth-child(3) span.price` rely on exact DOM structure. Site HTML updates break them silently.

**Mechanism:** Your selector worked yesterday:
```python
products = page.query_selector_all('div.product:nth-child(n)')  # Ordered by position
```
Today the site adds a banner ad or sidebar, shifting all children. Selector now matches wrong elements or none.

**Fix:** Use semantic selectors (class names, data attributes) instead of position:
```python
# BRITTLE: relies on order
products = page.query_selector_all('article:nth-child(n)')

# ROBUST: uses class
products = page.query_selector_all('article.product-card')

# ROBUST: uses data attribute
products = page.query_selector_all('[data-product-id]')
```

When a selector fails, log the raw HTML for debugging:
```python
products = page.query_selector_all('article.product-card')
if not products:
    html_snippet = page.content()[:500]  # First 500 chars
    print(f"[!] No products found. HTML: {html_snippet}", file=sys.stderr)
    # Log full HTML to file for manual inspection
    with open('data/debug_html.txt', 'w') as f:
        f.write(page.content())
    return []  # Return empty, cron will log failure
```

## Expired or Redirect Image URLs

**Pitfall:** Image URLs are temporary CDN links that expire after a few hours. Message sent 12h later includes broken image.

**Mechanism:** Product page serves images from a CDN:
```
https://cdn.example.com/cache/HASH.jpg?expires=1695123456
```
After expiry time, CDN returns 404. If Telegram tries to load the image hours later, it fails.

**Fix:** Cache images locally:
```python
import hashlib
from pathlib import Path
import shutil
import urllib.request

CACHE_DIR = Path("data/image_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def cache_image(image_url: str) -> str:
    """Download image, save locally, return local path."""
    # Hash the URL to get a unique filename
    img_hash = hashlib.md5(image_url.encode()).hexdigest()
    cached_path = CACHE_DIR / f"{img_hash}.jpg"
    
    # If already cached, return it
    if cached_path.exists():
        return str(cached_path)
    
    # Download and save
    try:
        urllib.request.urlretrieve(image_url, cached_path)
        return str(cached_path)
    except Exception as e:
        print(f"[!] Failed to cache image {image_url}: {e}", file=sys.stderr)
        return None  # Return None if cache fails

# In NDJSON output:
image_url = cache_image(original_url)
if image_url:
    output["image_url"] = image_url
else:
    # Omit image_url if caching failed; Claude will analyze without image
    pass
```

Then in Telegram message, upload the local file instead of URL:
```python
# Instead of embedding URL
message = f"![product]({image_url})"  # Won't work if image_url is temporary

# Use Hermes bot to upload and embed
# (requires bot to support file upload; check with `hermes send --help`)
```

## Text Content Mixed with Extra Whitespace

**Pitfall:** `element.text_content()` includes extra whitespace, line breaks, hidden text from CSS `::before` / `::after`.

**Mechanism:**
```html
<div class="product">
  <h2>Ingco Drill</h2>
  <p>Brand: Ingco
     Condition: New
     Stock: Yes
  </p>
</div>
```

`page.query_selector('.product').text_content()` returns:
```
Ingco Drill
Brand: Ingco
Condition: New
Stock: Yes
```
With extra line breaks and spaces. A regex looking for "Brand: (.+)" now has `\n` in the captured group.

**Fix:** Clean whitespace before parsing:
```python
text = element.text_content()
text_clean = ' '.join(text.split())  # Normalize whitespace to single spaces
# text_clean: "Ingco Drill Brand: Ingco Condition: New Stock: Yes"

# Now regex works
brand_match = re.search(r'Brand:\s*(.+?)(?:Condition|$)', text_clean)
if brand_match:
    brand = brand_match.group(1).strip()
```

Alternatively, use `element.text_content().strip()` and then split on `\n` if line breaks matter:
```python
lines = element.text_content().strip().split('\n')
for line in lines:
    line = line.strip()  # Remove leading/trailing space per line
    if line.startswith('Brand:'):
        brand = line.split(':', 1)[1].strip()
```

## JavaScript-Rendered Content

**Pitfall:** Content is loaded via JavaScript, but scraper fetches static HTML (no JS execution). Price, availability, or product count is 0.

**Mechanism:** HTML source contains:
```html
<div id="price-container"></div>
<script>
  fetch('/api/product/123').then(r => r.json()).then(data => {
    document.getElementById('price-container').textContent = data.price;
  });
</script>
```
A simple HTTP `requests.get()` returns the empty `<div>`. You see no price.

**Fix:** Use Playwright headless browser (already loaded) or wait for content:
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://example.com/products")
    
    # Wait for JS to populate content
    page.wait_for_selector('.price', timeout=5000)  # Wait up to 5s
    
    # Now extract
    price = page.query_selector('.price').text_content()
    
    browser.close()
```

## Multiple Matching Elements (Picking Wrong One)

**Pitfall:** Multiple elements match the selector; you grab the first one which is a header/template, not the actual data.

**Mechanism:**
```html
<template id="product-template">
  <div class="product-card">
    <h3 class="price">$0</h3>
  </div>
</template>

<div class="product-card">
  <h3 class="price">$199</h3>
</div>
```

If you use `page.query_selector('.price')`, you might get the template's `$0` instead of the real `$199`.

**Fix:** Be specific about which element to grab:
```python
# WRONG: gets first match, possibly a template
price = page.query_selector('.price').text_content()

# RIGHT: scope to visible product area
product_card = page.query_selector('main .product-card')  # main scope
if product_card:
    price = product_card.query_selector('.price').text_content()

# BETTER: exclude templates and hidden elements
visible_cards = page.query_selector_all('.product-card')
for card in visible_cards:
    # Skip if in template
    if card.closest('template'):
        continue
    # Skip if hidden (CSS display: none, visibility: hidden)
    if not card.is_visible():
        continue
    price = card.query_selector('.price').text_content()
    # Process...
```

## Store/Location Name Missing or Wrong

**Pitfall:** Store name is in a popup, tooltip, or loaded after page scroll. Static scraping gets empty value or a placeholder.

**Mechanism:**
```html
<div class="product-card">
  <h3>Ingco Drill</h3>
  <span class="store" data-store-id="123">Store Location</span>  <!-- Empty or placeholder -->
  <script>
    // Store loaded from API based on data-store-id
    const storeId = this.dataset.storeId;
    fetch(`/api/stores/${storeId}`).then(...).then(data => {
      this.textContent = data.location;
    });
  </script>
</div>
```

Static scraper sees `<span class="store">Store Location</span>` (placeholder text, not real store). Must execute JS or fetch API.

**Fix:** Wait for real content, or fetch API directly:
```python
# With Playwright (waits for JS):
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    page = p.chromium.launch().new_page()
    page.goto("...")
    page.wait_for_load_state('networkidle')  # Wait for JS to finish
    store = page.query_selector('.store').text_content()
    # Now store has real location

# Or fetch API directly:
import requests
import json

card_html = ...
store_id = card_html.get('data-store-id')
if store_id:
    store_resp = requests.get(f"https://example.com/api/stores/{store_id}")
    store_data = store_resp.json()
    store_location = store_data['location']
```

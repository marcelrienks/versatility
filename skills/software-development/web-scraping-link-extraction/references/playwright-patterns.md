# Playwright Link Extraction Patterns

Common e-commerce site link patterns and how to query them.

## Cash Converters (South Africa)

**Pattern:** `/shop/products/{slug}-{product_id}` or `/shop/products/{slug}` with optional store code suffix

```python
# Filter for product links
if href and "/shop/products/" in href and "login" not in href.lower():
    url = f"https://www.cashconverters.co.za{href}" if href.startswith("/") else href
```

**Pitfall:** Multiple links exist in the article (wishlist, product). Filter by path pattern, not position.

## Generic E-Commerce Pattern

When path pattern is unknown:

```python
# Log all links in first 3 products to identify pattern
if index <= 3:
    for i, link in enumerate(all_links):
        href = await link.get_attribute("href")
        text = await link.text_content()
        print(f"Link {i}: {href} | Text: {text[:40]}")
```

Then update filter based on most common path (e.g., `/item/`, `/products/`, `/product/`).

## Relative to Absolute Conversion

```python
def make_absolute(href, base_domain="https://example.com"):
    """Convert relative URL to absolute."""
    if href.startswith("http"):
        return href  # Already absolute
    if href.startswith("/"):
        return f"{base_domain}{href}"  # Root-relative
    # Path-relative (rare for product links, but handle it)
    return f"{base_domain}/{href}".replace("//", "/").replace(":///", "://")
```

## Handling Login Redirects

If all links are `/shop/login` or empty, the page may require authentication:

```python
# Option 1: Add auth cookies
context = await browser.new_context(
    storage_state="cookies.json"  # Pre-saved auth cookies
)
page = await context.new_page()

# Option 2: Wait longer for dynamic content
await page.wait_for_timeout(3000)  # More time for JS to render

# Option 3: Check if page renders links via JS (use networkidle)
await page.goto(url, wait_until="networkidle")  # Not just "domcontentloaded"
```

## Testing Link Validity

```python
import requests
from concurrent.futures import ThreadPoolExecutor

def check_url(url, timeout=5):
    try:
        resp = requests.head(url, allow_redirects=False, timeout=timeout)
        return url, resp.status_code
    except Exception as e:
        return url, str(e)

# Parallel validation
with ThreadPoolExecutor(max_workers=5) as pool:
    results = pool.map(check_url, urls)
    for url, status in results:
        if isinstance(status, int) and status >= 400:
            print(f"BROKEN: {url} ({status})")
```

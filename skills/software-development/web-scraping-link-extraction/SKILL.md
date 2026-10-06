---
name: web-scraping-link-extraction
description: "Extract product links from DOM, never construct them."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: software-development
    tags: [web-scraping, playwright, links, e-commerce, debugging]
    related_skills: [blocked-page-recovery]
---

# Web Scraping: Link Extraction Best Practice

When scraping product, article, or listing links from web pages, always extract URLs from the actual DOM. Never construct or synthesize URLs from page data (product names, IDs, slugs).

## Use When

- Scraping product links from e-commerce sites (Cash Converters, eBay, marketplace listings)
- Extracting article URLs from news or content sites
- Building a web scraper that outputs clickable links
- Debugging broken links in existing scrapers

## The Problem

**Synthetic URL construction** assumes you know the site's URL format and it never changes:

```python
# ❌ WRONG: Constructing URL from product name + ID
title_slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
url = f"https://site.com/shop/products/{title_slug}-{product_id}"
```

This fails when:
- URL format includes fields you don't have (e.g., store SKU codes appended: `{title}-{product_id}-{store_code}`)
- Page structure changes without notice
- Encoding or slug rules differ from your regex
- Login redirects or dynamic content prevents seeing the real link
- The site uses completely different URL patterns for different product categories

**Result:** All links point to wrong products, 404s, or login screens. Users click → failure.

## The Solution

**Query the actual `<a href>` links** in the article/product element. The DOM is the source of truth.

### Playwright Implementation

```python
async def extract_product_url(article_element, product_title: str):
    """Extract URL from actual DOM link, not synthetic construction."""
    url = ""
    try:
        # Query all links in the article
        all_links = await article_element.query_selector_all("a[href]")
        
        if all_links:
            # Filter for product links (skip login/wishlist)
            for link in all_links:
                href = await link.get_attribute("href")
                
                if href and "/products/" in href and "login" not in href.lower():
                    # Convert relative to absolute
                    if href.startswith("/"):
                        url = f"https://site.com{href}"
                    elif href.startswith("http"):
                        url = href
                    else:
                        url = f"https://site.com/{href}"
                    break  # Use first matching product link
        
        return url
        
    except Exception as e:
        print(f"Error extracting link for '{product_title}': {e}")
        return ""  # Return empty, don't crash
```

### Key Steps

1. **Query all links** in the article/product element (not page-wide)
2. **Identify product links** by path pattern (e.g., `/products/`, `/item/`, or domain-specific pattern)
3. **Filter out false positives** (login, wishlist, share links)
4. **Convert relative URLs to absolute** (prepend domain if needed)
5. **Return the first match** or continue searching if logic demands a specific link type

## Debugging Broken Links

**Symptom: All extracted URLs point to `/shop/login` or are identical wrong URLs**

1. **Inspect the live page** with Playwright in a temporary script:
   ```python
   async with async_playwright() as p:
       browser = await p.chromium.launch(headless=False)  # Show browser
       page = await browser.new_page()
       await page.goto("https://site.com/search?q=product")
       await page.wait_for_timeout(5000)  # Manual inspect
       # Right-click a product link, inspect element → find the `<a href>` and its container
   ```

2. **Log the raw HTML** during scraping:
   ```python
   inner_html = await article_element.inner_html()
   print(f"Article HTML: {inner_html[:500]}")  # First 500 chars
   # Look for `<a href="/shop/products/..." ...>` patterns
   ```

3. **Print all links found** in the article for the first few products:
   ```python
   if index <= 3:  # Debug first 3 only
       for i, link in enumerate(all_links):
           href = await link.get_attribute("href")
           text = await link.text_content()
           print(f"Link {i}: href={href} text='{text[:50]}'")
   ```

4. **Verify the filter logic** — check if your pattern match (`/products/`, `login` check, etc.) is too strict or too loose

5. **Check for page auth blocks** — if the page requires login to show real links, Playwright may not have auth cookies. Add:
   ```python
   # Optionally: context = await browser.new_context(storage_state="auth.json")
   # to persist cookies between runs
   ```

## Common Pitfalls

**Pitfall: Filtering for a link type that doesn't exist.** The product link may not have `/products/` in the path, or may use a different path entirely. Inspect the page first; do not assume a pattern. If no links match your filter, log the first few links found and adjust the filter.

**Pitfall: The site uses relative URLs, but you return them as-is.** Result: links are broken when displayed outside the scraper (Telegram, JSON file). Always convert relative URLs to absolute using the domain.

**Pitfall: Querying the whole page instead of the article element.** If the article contains multiple links (logo, ads, share buttons), you may grab the wrong one. Always scope to the article/product container: `article_element.query_selector_all("a[href]")`. 

**Pitfall: Not handling page structure changes.** If your scraper has been running for months, the site's HTML layout probably changed. When users report broken links, inspect the live page again before assuming your code is right. Add a dry-run mode: run the scraper on a single product manually, print the links found, and verify at least one is correct.

## Validation

After scraping, spot-check links:

```python
# Test script: verify URLs are valid before delivery
import requests
for product in products:
    url = product["url"]
    if url:  # Skip empty
        resp = requests.head(url, allow_redirects=False, timeout=5)
        if resp.status_code >= 400:
            print(f"BROKEN: {product['title']} → {url} (HTTP {resp.status_code})")
```

Do this on first run of a new scraper, or after site inspection reveals changes.

## References

- `references/playwright-patterns.md` — Site-specific link patterns (Cash Converters, generic e-commerce, auth handling, validation).

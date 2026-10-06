"""Web scraper for Cash Converters using Playwright."""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Ensure .local packages are in path for cron compatibility
home = os.path.expanduser("~")
local_site_packages = f"{home}/.local/lib/python3.9/site-packages"
if local_site_packages not in sys.path:
    sys.path.insert(0, local_site_packages)

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium", file=sys.stderr)
    sys.exit(1)

from config import (
    BASE_URL, SEARCH_INPUT_SELECTOR, PRODUCT_CONTAINER_SELECTOR, PRODUCT_ARTICLE_SELECTOR,
    HEADLESS, TIMEOUT_MS, WAIT_FOR_LOAD_MS, PLAYWRIGHT_CHANNEL, CACHE_DIR
)


class CashConvertersScraper:
    """Scrape products from Cash Converters SA."""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.search_selector = SEARCH_INPUT_SELECTOR
        self.container_selector = PRODUCT_CONTAINER_SELECTOR
        self.article_selector = PRODUCT_ARTICLE_SELECTOR
        self.timeout = TIMEOUT_MS
        self.wait_for_load = WAIT_FOR_LOAD_MS
        
    async def scrape_search_results(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Scrape all products for a given search term.
        
        Args:
            search_term: Product to search for
            
        Returns:
            List of product dictionaries with title, price, store, url, and image
        """
        products = []
        screenshot_path = None
        
        async with async_playwright() as p:
            browser = await p[PLAYWRIGHT_CHANNEL].launch(headless=HEADLESS)
            context = await browser.new_context(
                viewport={"width": 1024, "height": 768},
                user_agent="Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # Navigate to base URL
                print(f"[{search_term}] Loading {self.base_url}...", file=sys.stderr)
                await page.goto(self.base_url, wait_until="domcontentloaded", timeout=self.timeout)
                await page.wait_for_load_state("load", timeout=10000)
                await page.wait_for_timeout(3000)
                
                # Find and fill search input
                search_input = await page.query_selector(self.search_selector)
                if not search_input:
                    print(f"ERROR: Search input not found with selector", file=sys.stderr)
                    screenshot_path = await self._save_debug_screenshot(page, search_term, "search-input-not-found")
                    return products
                
                # Type search term (fill replaces content)
                await page.fill(self.search_selector, search_term)
                
                # Press Enter to search
                print(f"[{search_term}] Searching for '{search_term}'...", file=sys.stderr)
                await page.press(self.search_selector, "Enter")
                
                # Wait for results to load
                try:
                    await page.wait_for_selector(self.article_selector, timeout=self.timeout)
                except PlaywrightTimeoutError:
                    print(f"[{search_term}] No results found or timeout", file=sys.stderr)
                    screenshot_path = await self._save_debug_screenshot(page, search_term, "no-results-timeout")
                    return products
                
                # Additional wait for dynamic content
                await page.wait_for_timeout(self.wait_for_load)
                
                # Extract all product articles
                articles = await page.query_selector_all(self.article_selector)
                print(f"[{search_term}] Found {len(articles)} products", file=sys.stderr)
                
                for idx, article in enumerate(articles, 1):
                    try:
                        product = await self._extract_product_data(article, idx)
                        if product:
                            products.append(product)
                    except Exception as e:
                        print(f"[{search_term}] Error extracting product {idx}: {e}", file=sys.stderr)
                        continue
                
                print(f"[{search_term}] Successfully extracted {len(products)} products", file=sys.stderr)
                
                # If no products extracted but articles found, take screenshot for debugging
                if len(articles) > 0 and len(products) == 0:
                    screenshot_path = await self._save_debug_screenshot(page, search_term, "articles-found-but-none-extracted")
                    print(f"[{search_term}] DEBUG: Screenshot saved to {screenshot_path}", file=sys.stderr)
                
            except Exception as e:
                print(f"ERROR scraping {search_term}: {e}", file=sys.stderr)
                screenshot_path = await self._save_debug_screenshot(page, search_term, "scraper-exception")
                
            finally:
                await context.close()
                await browser.close()
        
        return products
    
    async def _save_debug_screenshot(self, page, search_term: str, reason: str) -> str:
        """Save a debug screenshot when errors occur."""
        try:
            from pathlib import Path
            debug_dir = Path(__file__).parent / "data" / "debug_screenshots"
            debug_dir.mkdir(exist_ok=True, parents=True)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = debug_dir / f"{search_term}_{reason}_{timestamp}.png"
            
            await page.screenshot(path=str(screenshot_path))
            print(f"[DEBUG] Screenshot saved: {screenshot_path}", file=sys.stderr)
            return str(screenshot_path)
        except Exception as e:
            print(f"[ERROR] Could not save debug screenshot: {e}", file=sys.stderr)
            return None
    
    async def _extract_product_data(self, article_element, index: int) -> Dict[str, Any]:
        """Extract data from a single product article element."""
        try:
            # Get all text content from article
            text_content = await article_element.text_content()
            
            # Get image first to extract product ID
            img_elem = await article_element.query_selector("img")
            image_url = ""
            product_id = ""
            
            if img_elem:
                image_url = await img_elem.get_attribute("src")
                # Extract product ID from image URL
                # Format: https://cc-prod.eu.saleor.cloud/media/thumbnails/products/15416647_479f1745_thumbnail_1024.webp
                import re
                id_match = re.search(r'/products/(\d+)_', image_url)
                if id_match:
                    product_id = id_match.group(1)
            
            # Parse text for title, price, store
            lines = [line.strip() for line in text_content.split("\n") if line.strip()]
            
            # Try smarter extraction using patterns
            title = ""
            price = ""
            store = ""
            category = ""
            
            # Look for price (starts with R followed by space and digits)
            import re
            price_match = re.search(r'R\s+([\d\s,]+)', text_content)
            if price_match:
                # Clean up the captured price: remove extra spaces, keep just digits and comma
                price_raw = price_match.group(1).strip()
                # Remove all spaces from within the number: "1 299" → "1299"
                price_clean = re.sub(r'\s+', '', price_raw)
                price = "R " + price_clean
                # Store is typically after price
                parts_after_price = text_content[price_match.end():].strip()
                # Look for "Store" keyword
                store_match = re.search(r'Store\s+(.+?)(?:Add|$)', parts_after_price)
                if store_match:
                    store = store_match.group(1).strip()
            
            # Extract product name - look for "Ingco" followed by model/product name
            product_match = re.search(r'Ingco\s+([A-Za-z0-9\s]+?)(?:R\s+\d+|Circular|Impact|Hand|Store|to your|$)', text_content)
            if product_match:
                title = "Ingco " + product_match.group(1).strip()
                # Clean up any remaining noise
                title = title.replace(" to your wishlist", "").replace(" to your", "").strip()
                
                # Strip store location patterns (e.g., "R 2 | Key West" becomes just title)
                # Remove patterns like " | [Store Location]" or "Store [Location]"
                title = re.sub(r'\s+\|\s+\w+.*$', '', title)  # Remove "|  Location"
                title = re.sub(r'\bStore\b\s+.*$', '', title)  # Remove "Store Location"
                title = title.strip()
            else:
                # Fallback: try to get first meaningful line
                for line in lines:
                    if line and not any(x in line.lower() for x in ['sign in', 'add to', 'wishlist', 'store']):
                        if line and len(line) > 2:
                            title = line
                            break
            
            # Category - look for tool type keywords
            tool_types = ['Circular Saw', 'Impact Wrench', 'Drill', 'Saw', 'Screwdriver', 'Hand Tools', 'Power Tools']
            for tool in tool_types:
                if tool.lower() in text_content.lower():
                    category = tool
                    break
            
            # Extract actual product URL from article link (DO NOT construct synthetically)
            url = ""
            try:
                # Look for ANY link in article that's not a "sign in" or wishlist link
                all_links = await article_element.query_selector_all("a[href]")
                
                if all_links:
                    # Find the product link (should contain "/shop/products/")
                    for link in all_links:
                        href = await link.get_attribute("href")
                        
                        if href and "/shop/products/" in href and "login" not in href.lower():
                            # This is a product link
                            if href.startswith("/"):
                                url = f"https://www.cashconverters.co.za{href}"
                            elif href.startswith("http"):
                                url = href
                            else:
                                url = f"https://www.cashconverters.co.za/{href}"
                            break  # Use first matching product link
                
                # Debug: only log empty URLs (failure case)
                if not url and index <= 3:
                    print(f"[{index}] WARNING: No product link found for '{title}'", file=sys.stderr)
                    for i, link in enumerate(all_links[:3]):
                        href = await link.get_attribute("href")
                        print(f"  Link {i}: {href}", file=sys.stderr)
                        
            except Exception as link_error:
                # If link extraction fails, log but continue (don't break product)
                print(f"[{index}] Error extracting link for '{title}': {link_error}", file=sys.stderr)
            
            return {
                "index": index,
                "product_id": product_id,
                "title": title,
                "category": category,
                "price": price,
                "store": store,
                "url": url,
                "image_url": image_url,
                "full_text": text_content
            }
            
        except Exception as e:
            print(f"Error extracting product element: {e}", file=sys.stderr)
            return None


async def main():
    """Command-line interface for scraper."""
    if len(sys.argv) < 2:
        print("Usage: python scraper.py '<search_term>'", file=sys.stderr)
        sys.exit(1)
    
    search_term = sys.argv[1]
    scraper = CashConvertersScraper()
    products = await scraper.scrape_search_results(search_term)
    
    # Output as JSON
    output = {
        "search_term": search_term,
        "timestamp": datetime.now().isoformat(),
        "count": len(products),
        "products": products
    }
    
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

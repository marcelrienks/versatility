#!/usr/bin/env python3
"""Cash Converters Product Hunter — Layer 1 (scrape + store).

Scrapes products from Cash Converters for every configured search term and
outputs raw NDJSON (one product per line) for the Hermes cron Agent (Layer 2)
to score and match. Also archives the full raw results to disk.

Layer 1 does NOT deduplicate — every run emits everything scraped, for every
search term, unconditionally. Deduplication is Layer 3's job
(send_formatter.py), which maintains the sent_products.json ledger right next
to the code that actually decides what gets delivered. See README.md for the
full 3-layer architecture and why dedup lives there.
"""

import sys
import json
import asyncio
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# CRITICAL: Add .local to path for cron compatibility
home = os.path.expanduser("~")
local_site_packages = f"{home}/.local/lib/python3.9/site-packages"
if local_site_packages not in sys.path:
    sys.path.insert(0, local_site_packages)

# Add script dir to path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_search_criteria, RESULTS_DIR, DATA_DIR
from scraper import CashConvertersScraper


class CashConvertersHunter:
    """Scrape products per search term and output NDJSON for the Agent."""

    def __init__(self):
        self.scraper = CashConvertersScraper()
        self.run_timestamp = datetime.now().isoformat()

    async def run(self) -> bool:
        """Run the hunt: scrape every search term, archive, output NDJSON."""
        try:
            criteria = load_search_criteria()
            if not criteria:
                print("ERROR: No search criteria configured", file=sys.stderr)
                return False

            print(f"Loaded {len(criteria)} search criteria", file=sys.stderr)

            all_results = []
            for item in criteria:
                search_term = item.get("search_term")
                context = item.get("context")

                if not search_term or not context:
                    print(f"Skipping invalid criteria: {item}", file=sys.stderr)
                    continue

                print(f"Searching: {search_term}", file=sys.stderr)
                result = await self._search(search_term, context)
                all_results.append(result)

            self._save_results(all_results)
            self._cleanup_old_results()
            self._cleanup_old_images()
            self._output_ndjson(all_results)

            return True

        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False

    async def _search(self, search_term: str, context: str) -> Dict[str, Any]:
        """Search for products for one search term."""
        result = {
            "search_term": search_term,
            "context": context,
            "products_found": 0,
            "products": [],
            "error": None,
        }

        try:
            products = await self.scraper.scrape_search_results(search_term)
            result["products_found"] = len(products)
            result["products"] = products

            if products:
                print(f"Scraped {len(products)} products for '{search_term}'", file=sys.stderr)
            else:
                print(f"No products found for: {search_term}", file=sys.stderr)

            return result

        except Exception as e:
            print(f"Error searching '{search_term}': {e}", file=sys.stderr)
            result["error"] = str(e)
            return result

    def _output_ndjson(self, all_results: List[Dict]) -> None:
        """Output one product per line (NDJSON), unconditionally, no dedup.

        The cron Agent (Layer 2) consumes this stream directly to score and
        match. If a search produced zero products across the board, emit a
        single NO_PRODUCTS summary line so the Agent (and anyone reading cron
        history) can tell "nothing scraped" apart from "scraped but no
        matches" (the latter is silent by design further down the pipeline).
        """
        output_count = 0

        for search_result in all_results:
            search_term = search_result.get("search_term")
            context = search_result.get("context")
            products = search_result.get("products", [])

            for product in products:
                print(json.dumps({
                    "search_term": search_term,
                    "context": context,
                    "product": product,
                }))
                output_count += 1

        if output_count == 0:
            print(json.dumps({
                "message_type": "NO_PRODUCTS",
                "status": "SUMMARY",
                "description": "No products found in any searches this run. Check search terms or website availability.",
                "timestamp": datetime.now().isoformat(),
            }))

        print(f"Output: {output_count} products across {len(all_results)} searches", file=sys.stderr)

    def _save_results(self, all_results: List[Dict]) -> None:
        """Save raw results to JSON for record-keeping."""
        results_file = RESULTS_DIR / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        output = {
            "timestamp": self.run_timestamp,
            "searches": all_results,
        }

        with open(results_file, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Saved results to {results_file}", file=sys.stderr)

    def _cleanup_old_results(self, keep_count: int = 30) -> None:
        """Remove old result files, keeping only the last N files."""
        try:
            result_files = sorted(RESULTS_DIR.glob("results_*.json"), reverse=True)

            if len(result_files) > keep_count:
                to_delete = result_files[keep_count:]
                for f in to_delete:
                    f.unlink()
                    print(f"Deleted old result file: {f.name}", file=sys.stderr)

                print(f"Cleanup: Kept last {keep_count} result files, deleted {len(to_delete)}",
                      file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error during result cleanup: {e}", file=sys.stderr)

    def _cleanup_old_images(self, days_to_keep: int = 30) -> None:
        """Remove image cache files older than N days."""
        try:
            image_dir = DATA_DIR / "image_cache"
            if not image_dir.exists():
                return

            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            cutoff_timestamp = cutoff_time.timestamp()

            deleted_count = 0
            for image_file in image_dir.glob("*.webp"):
                if image_file.stat().st_mtime < cutoff_timestamp:
                    image_file.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                print(f"Cleanup: Deleted {deleted_count} image cache files older than {days_to_keep} days",
                      file=sys.stderr)
        except Exception as e:
            print(f"Warning: Error during image cleanup: {e}", file=sys.stderr)


async def main():
    """Entry point."""
    try:
        hunter = CashConvertersHunter()
        success = await hunter.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

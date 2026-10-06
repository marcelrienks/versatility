---
name: cash-converters-automation
description: "Automate secondhand product hunting on Cash Converters."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: automation
    tags: [web-scraping, playwright, ai-analysis, telegram, secondhand, ecommerce]
    related_skills: [blocked-page-recovery]
---

# Cash Converters Daily Product Hunter

Fully automated daily product hunting on Cash Converters (South Africa). Scrapes, analyzes with Claude AI, sends matches to Telegram.

## Use When

You want to monitor a secondhand retail site (Cash Converters) for products matching your criteria, without manual checking. Fully hands-off after setup.

## What It Does

1. **Scrapes** — Playwright headless browser loads each search term, extracts products
2. **Analyzes** — Claude AI evaluates each product against your context requirements
3. **Filters** — Keeps only high-confidence matches (≥60% score default)
4. **Notifies** — Sends matched products to Telegram with links, prices, stores, **and inline product images**
5. **Logs** — Saves full JSON results for history

## Architecture (Consolidated Oct 2026)

**Single cron job, 2 layers:**
- **Layer 1 (Script):** `orchestrator.py` scrapes products, outputs NDJSON
- **Layer 2 (Agent):** Claude AI scores, deduplicates, formats, sends to Telegram

Previously a 2-job architecture (scrape job → dedup job) has been consolidated into one.
The agent now handles scoring + deduplication + formatting inline. No intermediate files.

## Files

All code lives in: `~/.hermes/scripts/cash_converters/`

- `orchestrator.py` — Scraper orchestrator (runs searches, outputs JSON for Hermes)
- `scraper.py` — Playwright web scraper (async, headless)
- `config.py` — Configuration + search criteria
- `data/search_criteria.json` — Your product watchlist (search_term + context)
- `data/results/` — Raw results archive (timestamped JSON)

## Setup

### 1. Install dependencies

```bash
pip install playwright requests
playwright install chromium
```

### 2. Configure Telegram integration

Ensure your Hermes session has Telegram configured. Hermes Agent handles all delivery — no API keys needed in scripts.

### 3. Edit search criteria

```bash
nano ~/.hermes/scripts/cash_converters/data/search_criteria.json
```

Format:
```json
[
  {
    "search_term": "laptop",
    "context": "Looking for functional second-hand laptops suitable for daily work"
  }
]
```

Context is critical — Hermes Agent's Claude uses it to determine if products match your needs.

### 4. Verify the cron job — automatic, single job

**Single job, consolidated architecture (Oct 2026):**

The cron job is already created. It runs daily at 09:00:
```bash
hermes cron list | grep "Daily Hunt"
```

**How it works:**
1. **Layer 1:** `orchestrator.py` scrapes all products, outputs raw NDJSON to stdout
2. **Layer 2:** Hermes Agent receives NDJSON, for each product:
   - Scores 0-100 vs. search context
   - Keeps score >= 60
   - Checks `data/sent_products.json` ledger for NEW/PRICE_CHANGE/DUPLICATE
   - Updates ledger (read-merge-write)
   - Formats output as `---`-delimited blocks
   - Emits final response (empty if zero matches)
3. **Telegram:** Cron delivery gateway splits on `---` and sends one message per block

## How It Works

### Layer 1: Python Script (Deterministic Scraping)

**Orchestrator.py:**
- Loads search criteria (search_term + context pairs)
- For each search term, calls scraper.py
- Outputs NDJSON to stdout (one product per line):
  ```json
  {"search_term": "...", "context": "...", "product": {...}}
  ```
- Archives raw results to `data/results/results_YYYYMMDD_HHMMSS.json`
- Cleans old results and images

**Scraper.py:**
- Headless Chromium via Playwright (async)
- Navigates to Cash Converters
- Types search term, presses Enter
- Extracts product title, price, store, URL, product_id
- Returns JSON list of products

### Layer 2: Hermes Agent (Intelligence + Delivery)

When the cron job fires, NDJSON is injected into the agent prompt. The agent:

1. **Scores** each product 0-100 against its search context
   - Judges: price reasonable for secondhand? condition acceptable? matches intent?
   - Filters: keeps only score >= 60

2. **Deduplicates** against `data/sent_products.json` ledger:
   - **NEW:** product_id not in ledger → include
   - **PRICE_CHANGE:** same product_id, new price → include (note the change)
   - **DUPLICATE:** same product_id, same price → skip silently

3. **Updates ledger** (read-merge-write pattern):
   - Reads current ledger
   - For each NEW/PRICE_CHANGE, adds/overwrites entry
   - Merges with untouched entries
   - Writes back as valid JSON

4. **Formats output** as `---`-delimited blocks:
   - **NEW:** title + link + price | store + confidence/100
   - **PRICE_CHANGE:** 🔔 PRICE UPDATE + title + link + old → NEW price + confidence/100
   - Empty response if zero matches (no spurious message)

5. **Emits final response** → cron gateway → Telegram adapter splits on `---` → one message per block

## Performance

- **Scraping**: ~2-3 sec per search (page load + extraction)
- **Hermes Agent Analysis**: ~2-5 sec per product (Claude API)
- **Total**: Typical 2-3 searches × 10-20 products = ~1-2 minutes
- Async scraper keeps web operations fast
- Agent analysis happens once per job run, not repeated

Faster than previous version due to eliminated redundant AI calls and simplified architecture.

## Rich Media: Inline Product Images

Each matched product now displays with its product image embedded directly in the Telegram message.

**How it works:**
1. Scraper extracts product image URL from product listing
2. Formatter includes image in markdown format: `![Product Image](image-url)`
3. Hermes Agent renders the markdown when sending to Telegram
4. Telegram displays image inline, followed by product details

**Result:** Each matched product shows as a rich card:
```
1. [Product Title](link-to-product)
   💰 Price | 🏪 Store
   ![Product Image](url-to-image)
   ⭐ Score/100 match
   📝 Recommendation
```

Images are cached thumbnails from Cash Converters CDN, fast and reliable.

## Product Deduplication & Price Change Detection

**How it works:**

1. **Sent Products Tracking**: `data/sent_products.json` stores all products that have been sent to Telegram:
   - `product_id` (extracted from image URL)
   - `title`, `price`, `url`, `sent_at`, `search_terms`

2. **Deduplication Logic**:
   - **NEW**: Product ID never seen before → send to Telegram
   - **PRICE_CHANGE**: Same product ID but price differs → send with price update
   - **DUPLICATE**: Same product ID and price → skip silently

3. **Output to Hermes Agent**:
   - NDJSON with `status` field ("NEW" or "PRICE_CHANGE")
   - For PRICE_CHANGE: includes `previous_price` for comparison
   - Duplicates filtered out in orchestrator (never reach Agent)
   - Summary messages for empty states:
     - `message_type: "NO_PRODUCTS"` — no products found in any search
     - `message_type: "NO_CHANGES"` — products found but all duplicates (no new/updates)

4. **Telegram Message Format**:
   - NO_PRODUCTS summary: ⚠️ status message confirming cron ran
   - NO_CHANGES summary: ✅ status message confirming cron ran with duplicate count
   - NEW: Standard (title, price, store, score)
   - PRICE_CHANGE: 🔔 **PRICE UPDATE** 🔔 header + old → **NEW** prices (bold)

5. **Persistence**:
   - sent_products.json updated after each run
   - Can be manually edited to reset tracking

## FIXES APPLIED (2026-09-23)

### Issue 1: "R 2" Store Location in Product Title
**Status: FIXED** ✅

Problem: Titles showed "Ingco Cosli250511 R 2 | Key West" instead of clean "Ingco Cosli250511".

Solution: Added regex stripping in `scraper.py` (lines 188-190):
```python
# Strip store location patterns
title = re.sub(r'\s+\|\s+\w+.*$', '', title)  # Remove "|  Location"
title = re.sub(r'\bStore\b\s+.*$', '', title)  # Remove "Store Location"
```

Now outputs: "Ingco Cosli250511" (location in separate `store` field only).

### Issue 2: Two Links Per Telegram Message
**Status: FIXED** ✅

Problem: Each message showed product URL + image URL (both as links).

Solution: Updated cron job prompt (job ID: `04ff6d3c1fdb`) to explicitly instruct Agent:
```
ONLY include: [title](product_url) — NO image link
Do NOT include image_url or embed images — Telegram will auto-preview from product_url
```

Now outputs: ONE link per product (product page only). Telegram auto-previews.

## Customization

### Change match threshold (confidence score)

Edit the cron job prompt to change the minimum score. Default is >=60:

```
hermes cron update <job-id> --prompt="...
keep >=70  # stricter (only high confidence)
keep >=50  # looser (more options)
..."
```

### Add more search terms

Edit `~/.hermes/scripts/cash_converters/data/search_criteria.json`:
```json
[
  {"search_term": "laptop", "context": "functional workstation"},
  {"search_term": "monitor", "context": "27-inch gaming, good condition"},
  {"search_term": "keyboard", "context": "mechanical, 80%+ size"}
]
```

### Adjust schedule

```bash
hermes cron update <job-id> --schedule="every weekday at 09:00"
hermes cron update <job-id> --schedule="0 12 * * *"  # noon
```

### Pause/resume

```bash
hermes cron pause <job-id>
hermes cron resume <job-id>
```

## Troubleshooting

**Missing Playwright:**
```bash
pip install playwright
playwright install chromium
```

**No Telegram messages:**
- Verify Hermes session has Telegram bot configured (check Settings → Integrations)
- Check job delivery is set to 'telegram' (not 'local')
- Verify cron job ran: `hermes cron list` shows last_run_at

**No products found:**
- Search term may not exist on Cash Converters
- Try broader terms ("laptop" vs specific model)
- Check site structure hasn't changed
- Manual test: `cd ~/.hermes/scripts/cash_converters && python3 orchestrator.py`

**Products scraped but no Telegram delivery:**
- Check Hermes Agent ran: see cron job last_run_at and last_status
- Verify Claude API key is set (Hermes needs this for analysis)
- Check terminal/cron output logs for errors

**Context too strict (no matches):**
- Broaden the context sentence (less specific)
- Lower the minimum confidence score (change >=60 to >=50)
- Review Claude's reasoning in Hermes Agent output

## Key Lessons

### Scripts = Data, Agent = Intelligence
Separation of concerns: Python scripts handle scraping (deterministic, repeatable), Hermes Agent handles analysis (reasoning, filtering, delivery). No embedded AI in scripts.

### Context is Critical
The context sentence you provide determines match quality. Bad context = false negatives. Examples:
- Bad: "laptop"
- Good: "Functional MacBook Pro 13-inch from 2018+ for software development"

### Hermes Gateway Eliminates Config
No hardcoded API keys, tokens, or credentials in scripts. Hermes Agent's Telegram integration is configured once globally and reused by all jobs.

### Async Scraping is Fast
Playwright async operations mean scraping N search terms happens in parallel, not sequentially. Large speedup with many searches.

### Results are Archived
Every run saves full JSON to `data/results/`. Useful for tracking trends, debugging, auditing matches over time.

### Confidence Scoring > Binary Yes/No
Claude scores 0-100 instead of yes/no. This lets you filter by confidence and see reasoning in Telegram. Much more reliable than binary matching.

## Refs

- Playwright docs: https://playwright.dev/python/
- Claude API: https://docs.anthropic.com/
- Telegram Bot API: https://core.telegram.org/bots/api
- Hermes cron: `hermes cron --help`

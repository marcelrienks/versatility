# Cash Converters Daily Product Hunter

Automated daily product hunting on Cash Converters (South Africa). Scrapes products per search term, has an LLM agent score/match them against your criteria, deduplicates against a persistent ledger, then sends Telegram messages for new/changed products — fully automated via a single Hermes cron job.

**Location:** `~/.hermes/scripts/cash_converters/`

## Architecture (2 layers, 1 cron job)

**Latest update (2026-10-06):** Added automatic cleanup of old ledger entries and cache files (>90 days). Merged two jobs into one. The Agent now handles scoring + deduplication + formatting inline, emitting the final Telegram-ready output.

This project is split into two logical layers:
- **Layer 1 (Script):** Deterministic scraping — loads search criteria, scrapes products, outputs NDJSON, runs cleanup.
- **Layer 2 (Agent):** Intelligent filtering — scores products, deduplicates against persistent ledger, formats output for Telegram, updates tracking.

Both layers run inside a single cron job:

```
Layer 0: CLEANUP (before writes)
┌──────────────────────────────────────┐
│ cleanup_ledger() + cleanup_files()   │
│ - Remove ledger entries > 90 days old│
│ - Delete cache/log files > 90 days   │
│ - Backup ledger before write         │
│ - Log to stderr, non-blocking        │
└──────────────────────────────────────┘
                    │
                    ▼
Layer 1: SCRAPE + STORE (deterministic)
┌──────────────────────────────────────┐
│ orchestrator.py runs:                │
│ - load search_criteria.json           │
│ - per search term:                    │
│   • scrape all products               │
│   • output NDJSON (stdout)            │
│   • archive raw results to disk       │
│   • clean old results & images        │
└──────────────────────────────────────┘
                    │
                    │ NDJSON stream
                    │ (injected into agent prompt)
                    ▼
Layer 2: AGENT SCORE + DEDUP + FORMAT + SEND
┌──────────────────────────────────────┐
│ Cron Job A (agent, deliver=telegram) │
│                                      │
│ For each product in NDJSON stream:  │
│ 1. Score 0-100 vs. search context   │
│ 2. Keep if score >= 60              │
│ 3. Check against ledger             │
│    (data/sent_products.json):       │
│    - NEW: product_id not seen       │
│    - PRICE_CHANGE: same ID, new $   │
│    - DUPLICATE: same ID, same $ → skip
│ 4. Update ledger with NEW/CHANGES   │
│ 5. Format output:                   │
│    - One "---"-delimited block      │
│      per NEW/PRICE_CHANGE product   │
│    - Empty response if zero matches │
│                                      │
│ Final response sent via cron         │
│ delivery to Telegram                │
└──────────────────────────────────────┘
                    │
                    │ formatted text
                    │ (split on "---")
                    ▼
            Telegram adapter
         sends one message per block
```

## Deduplication Logic

Products are classified into three categories:

### NEW
- **Condition:** `product_id` not in ledger
- **Action:** Include in output, add to ledger with current timestamp
- **Output:** Standard product block with title, URL, price, store, confidence

### PRICE_CHANGE
- **Condition:** `product_id` in ledger AND current price differs from stored price
- **Action:** Include in output (note the change), update ledger price + timestamp
- **Output:** Block prefixed with `🔔 PRICE UPDATE`, shows previous → new price

### DUPLICATE
- **Condition:** `product_id` in ledger AND current price matches stored price
- **Action:** Silently drop (no output, no user notification)
- **Ledger:** Entry unchanged, timestamp unchanged

**Ledger file:** `data/sent_products.json` (JSON object keyed by `product_id`)

Example entry:
```json
{
  "15485113": {
    "product_id": "15485113",
    "title": "Ingco Cosli250511",
    "price": "R 2999",
    "url": "https://www.cashconverters.co.za/shop/products/ingco-cosli250511-bbkey007770",
    "sent_at": "2026-10-06T09:01:35.000000",
    "search_terms": ["ingco"]
  }
}
```

## Automatic Cleanup

Every cron run starts by cleaning old data (before any scraping or writes):

**Cleanup targets (>90 days old):**
1. Ledger entries with `sent_at` > 90 days in the past
2. Scrape cache files (`data/scrape_cache/`) with mtime > 90 days
3. Log files (`logs/`) with mtime > 90 days

**Behavior:**
- Creates `.bak` backup of ledger before modifying
- Logs to stderr: `Cleanup: Removed X ledger entries (>90 days old)`
- Non-blocking: errors logged, job continues
- Idempotent: safe to run multiple times per job
- JSON validated before and after write

This prevents the ledger and cache from growing indefinitely over time.

## Why One Job Now

**Before (2 jobs):**
- Job A (09:00, agent): Score products, write pending_matches.jsonl
- Job B (09:10, no_agent): Dedup pending_matches.jsonl, format, send to Telegram

**After (1 job):**
- Job A (09:00, agent): Score → Dedup → Format → Send (all in agent prompt)
- Job B removed (redundant)
- Cleanup phase added (runs first, non-blocking)

**Benefits:**
- Simpler scheduling (one job instead of two)
- No intermediate files (pending_matches.jsonl eliminated)
- Ledger (sent_products.json) read/written only by the agent (deterministic)
- Same dedup + price-change logic, just integrated into the prompt
- Automatic cleanup prevents bloat
- Easier to test and debug (fewer moving parts)

## Platform Constraints

The design respects two hard Hermes platform rules:

1. **Cron agents never get `send_message` tool** — messaging toolset is unconditionally stripped
   for cron jobs (loop prevention). So the agent can't directly call Telegram API; it must
   emit text for the cron delivery gateway to send.

2. **`TELEGRAM_BOT_TOKEN` never reaches cron scripts** — Tier-1 secret, always stripped from
   child processes, not overrideable. Only the gateway (holding the real token) can send.

**Solution:** The agent emits formatted text (final response), the cron delivery gateway
hands it to the live Telegram adapter. The adapter has a local patch (`_split_products_with_images()`
in `plugins/platforms/telegram/adapter.py`) that splits on `\n---\n` and sends each block
as its own message.

## Files

All code lives in: `~/.hermes/scripts/cash_converters/`

| File | Purpose |
|------|---------|
| `run_scrape.sh` | Job entry point (runs orchestrator.py) |
| `orchestrator.py` | Scraper orchestrator (searches, outputs NDJSON, archives results) |
| `scraper.py` | Playwright headless browser (async product extraction) |
| `config.py` | Configuration + search criteria loading |
| `data/search_criteria.json` | Your product watchlist (search_term + context) |
| `data/sent_products.json` | Ledger of all sent products (product_id → {title, price, sent_at, ...}) |
| `data/results/` | Raw results archive (timestamped JSON, one per run) |
| `data/image_cache/` | Product image cache (thumbnails from Cash Converters CDN) |
| `data/scrape_cache/` | Temporary scrape cache (cleaned after 90 days) |
| `logs/` | Job logs (cleaned after 90 days) |

**Removed files (consolidation):**
- `send_formatter.py` — dedup logic moved to agent prompt
- `run_send.sh` — Job B deleted (was no_agent script)

## Setup

### 1. Install dependencies

```bash
pip install playwright requests
playwright install chromium
```

### 2. Configure Telegram integration

Hermes Agent handles all delivery — no API keys needed in scripts.

### 3. Edit search criteria

```bash
nano ~/.hermes/scripts/cash_converters/data/search_criteria.json
```

Format:
```json
[
  {
    "search_term": "ingco",
    "context": "power and hand tool brand (yellow and brown)"
  },
  {
    "search_term": "makita",
    "context": "professional cordless drill, 18V or higher"
  }
]
```

Context is critical — Claude uses it to score relevance and assess condition/price reasonableness.

### 4. Verify the cron job

```bash
hermes cron list
```

You should see: "Cash Converters Daily Hunt", daily at 09:00, deliver=telegram.

The job's agent prompt handles scoring, dedup, ledger updates, cleanup, and formatting.

## How It Works

### Layer 0: Cleanup Phase

At the very start of the cron job, before any scraping:

1. **Ledger cleanup:** Load `sent_products.json`, remove entries with `sent_at` > 90 days old
2. **File cleanup:** Delete cache files in `data/scrape_cache/` and log files with mtime > 90 days old
3. **Backup:** Create `.bak` backup before modifying ledger
4. **Logging:** Report to stderr (non-blocking, doesn't interfere with job output)

This runs automatically every cron execution.

### Layer 1: Script Phase (Scraping)

`orchestrator.py` runs inside the cron job:
1. Loads search criteria from `data/search_criteria.json`
2. For each search term, calls `scraper.py` to scrape products
3. Outputs NDJSON to stdout (one product per line):
   ```json
   {"search_term": "ingco", "context": "power and hand tool brand (yellow and brown)", "product": {"product_id": "15485113", "title": "Ingco Cosli250511", "price": "R 2999", ...}}
   ```
4. Archives raw results to `data/results/results_YYYYMMDD_HHMMSS.json`
5. Cleans old results (keeps last 30)
6. Cleans old images (keeps last 30 days)

The NDJSON output is automatically injected into the agent prompt.

### Layer 2: Agent Phase (Scoring, Dedup, Formatting)

The cron Agent receives NDJSON and:

1. **Scores** each product 0-100 against its search context
   - Judges: price reasonable for secondhand? condition acceptable? matches intent?
   - Filters: keeps only score >= 60

2. **Deduplicates** against the ledger (`data/sent_products.json`):
   - **NEW:** product_id not in ledger → include in output
   - **PRICE_CHANGE:** same product_id, new price → include (note the change)
   - **DUPLICATE:** same product_id, same price → skip silently

3. **Updates ledger:**
   - Reads current ledger (JSON object keyed by product_id)
   - For each NEW/PRICE_CHANGE product, adds/overwrites entry with current timestamp
   - Merges with untouched entries
   - Writes back as valid JSON (read-merge-write pattern)

4. **Formats output** as `---`-delimited blocks:
   - **NEW product:**
     ```
     Ingco Cosli250511
     https://www.cashconverters.co.za/shop/products/ingco-cosli250511-bbkey007770
     R 2999 | Key West
     Confidence: 90/100
     ```
   - **PRICE_CHANGE product:**
     ```
     🔔 PRICE UPDATE
     Ingco Cosli250511
     https://www.cashconverters.co.za/shop/products/ingco-cosli250511-bbkey007770
     Previous: R 1 -> NEW: R 2999 | Key West
     Confidence: 90/100
     ```
   - Blocks joined with blank line + `---` + blank line
   - Empty response if zero matches (no spurious Telegram message)

5. **Emits final response** (the only thing the agent outputs)
   - Text is delivered by cron gateway to Telegram
   - Adapter splits on `---` and sends one message per block
   - Empty response = no messages sent

## Performance

- **Cleanup:** ~100ms (fast JSON read/write)
- **Scraping:** ~2-3 sec per search (page load + extraction, async parallel)
- **Agent scoring:** ~2-5 sec per product (Claude API)
- **Total:** Typical 2-3 searches × 10-20 products = ~1-2 minutes

Async scraper keeps web operations fast. Cleanup is non-blocking.

## Customization

### Change match threshold

Edit the cron job prompt (via `hermes cron edit <job_id>`):
```
If score >= 60  →  keep >= 70 (stricter) or >= 50 (looser)
```

### Add more search terms

Edit `data/search_criteria.json`:
```json
[
  {"search_term": "ingco", "context": "power and hand tool brand (yellow and brown)"},
  {"search_term": "makita", "context": "professional cordless drill"},
  {"search_term": "bosch", "context": "impact driver or angle grinder"}
]
```

### Adjust cleanup threshold

Edit `orchestrator.py`, call to `cleanup_ledger()`:
```python
cleanup_ledger(ledger_path, days=180)  # 6 months instead of 90 days
```

### Adjust schedule

```bash
hermes cron edit <job_id> --schedule="every weekday at 09:00"
hermes cron edit <job_id> --schedule="0 12 * * *"  # noon
```

### Pause / Resume

```bash
hermes cron pause <job_id>
hermes cron resume <job_id>
```

## Testing

### Clear ledger to test all products as NEW

```bash
echo '{}' > ~/.hermes/scripts/cash_converters/data/sent_products.json
rm -rf ~/.hermes/scripts/cash_converters/data/cache/*
rm -rf ~/.hermes/scripts/cash_converters/data/results/*
```

Now the next run will treat all products as NEW and send them all.

### Manual test

```bash
cd ~/.hermes/scripts/cash_converters
python3 orchestrator.py
```

This outputs NDJSON (not formatted for Telegram, but lets you verify scraping works).

## Troubleshooting

**Missing Playwright:**
```bash
pip install playwright
playwright install chromium
```

**No Telegram messages:**
- Verify Telegram is configured (Settings → Integrations)
- Check job delivery is set to `telegram` (not `local`)
- Verify job ran: `hermes cron list` shows `last_run_at`
- Check cron history: `hermes cron history <job_id> | head -5`

**No products found:**
- Search term may not exist on Cash Converters
- Try broader terms (`"ingco"` vs specific model)
- Check site structure hasn't changed
- Manual test: `cd ~/.hermes/scripts/cash_converters && python3 orchestrator.py`

**Products scraped but no Telegram delivery:**
- Check Agent ran: see cron history status
- Verify Claude API key is set (Hermes needs this)
- Check terminal/cron logs for errors
- Inspect `data/sent_products.json` for ledger corruption

**Context too strict (no matches):**
- Broaden context sentence (less specific)
- Lower confidence threshold (>=60 → >=50)
- Review Claude's reasoning in cron history

**Price change not detected:**
- Verify `product_id` is consistent across runs (from scraper)
- Check `data/sent_products.json` contains the old product entry
- Manually inspect the product details to confirm price actually changed

**Ledger corrupted:**
- Restore from `.bak` backup: `cp data/sent_products.json.bak data/sent_products.json`
- Or clear and restart: `echo '{}' > data/sent_products.json`

## Key Lessons

### Scripts = Data, Agent = Intelligence

Python scripts handle scraping (deterministic, repeatable). Agent handles analysis (reasoning, filtering, delivery). Cleanup happens at the start (non-blocking). Separation of concerns means each layer is simple.

### Context is Critical

The context sentence determines match quality. Examples:
- **Bad:** `"ingco"`
- **Good:** `"Power and hand tool brand (yellow and brown), cordless drills and impact wrenches preferred"`

### Deduplication Prevents Noise

The persistent ledger (`sent_products.json`) ensures you don't get the same product twice. Price changes are detected and flagged. Cleanup removes old entries automatically.

### Hermes Gateway Eliminates Config

No hardcoded API keys, tokens, or credentials in scripts. Hermes Agent's Telegram integration is configured once globally.

### Async Scraping is Fast

Playwright async operations mean scraping N search terms happens in parallel. Large speedup with many searches.

### Results are Archived

Every run saves full JSON to `data/results/`. Useful for tracking trends, debugging, auditing matches over time.

### Confidence Scoring > Binary Yes/No

Claude scores 0-100 instead of yes/no. This lets you filter by confidence level and see reasoning. More reliable than binary matching.

### Ledger = Single Source of Truth

`data/sent_products.json` is the only dedup source. It's read and written only by the agent prompt (no race conditions). Manually edit it to reset tracking for a product.

### Cleanup Prevents Bloat

Automatic cleanup (>90 days) means the ledger and cache never grow indefinitely. Data stays recent and relevant.

## References

- Playwright docs: https://playwright.dev/python/
- Claude API: https://docs.anthropic.com/
- Telegram Bot API: https://core.telegram.org/bots/api
- Hermes cron: `hermes cron --help`
- Cash Converters: https://www.cashconverters.co.za/

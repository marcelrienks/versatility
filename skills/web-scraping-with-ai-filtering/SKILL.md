---
name: web-scraping-with-ai-filtering
description: "Scrape items, filter via AI, deliver per-item."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: automation
    tags: [web-scraping, ai-filtering, streaming, ndjson, hermes-cron, telegram, per-item-delivery]
    related_skills: [cash-converters-automation]
---

# Web Scraping with AI Filtering & Per-Item Delivery

## Use When

You need to:
- Scrape a website or feed for products, jobs, listings, or any repeated items
- Filter items using AI (Claude) against custom criteria (context/quality/relevance)
- Deliver each matching item as a **separate message** (Telegram, email, Discord, etc.)
- Run daily, weekly, or on-demand via Hermes cron

Examples: secondhand marketplaces, job boards, rental sites, price tracking, competitor monitoring.

## Key Insight: NDJSON for Per-Item Delivery

The critical constraint: **each matched item gets its own separate message, never batched**. This is achieved by:

1. **Scraper outputs NDJSON** (one item per line, not one array)
2. **Agent processes line-by-line** (reads each line independently)
3. **Agent sends immediately** (one message per match, does not accumulate)

If scraper outputs a single JSON array, or if the agent waits to collect matches before sending, messages will batch and violate the one-per-item requirement. NDJSON + immediate send is non-negotiable for this pattern.

## Architecture: Two Patterns

### Pattern A: Agent-Driven Delivery (Recommended for Filtering Logic)

```
Python Scraper (deterministic, fast)
  ├─ Load criteria (search terms + contexts)
  ├─ Headless browser (Playwright) or HTTP requests
  ├─ Extract: title, URL, price/metadata, image_url, description
  └─ Output: NDJSON (one item per line, stdout only)
        └─ EACH LINE: {search_term, context, item: {title, url, image_url, ...}}

Hermes Cron Job (LLM-driven filtering)
  ├─ Receives script output (NDJSON stream)
  ├─ Processes line-by-line (ONE item at a time)
  ├─ Claude AI: Score 0-100 confidence (item vs context)
  ├─ Filter: Keep ≥threshold (default 60)
  └─ Deliver: ONE message per match via `---` block separators (Telegram/email/Discord)
        └─ Message format: title + link + image + price + confidence + reasoning
```

**When to use:** Filtering logic is complex or context-dependent. Agent sees images and makes nuanced decisions. Fine-tuning is prompt-only (no code changes).

### Pattern B: Direct Script Delivery (Full Control, No Agent)

```
Python Scraper (deterministic, fast + delivery)
  ├─ Load criteria (search terms + contexts)
  ├─ Scrape: title, URL, price/metadata, image_url, description
  ├─ For EACH item:
  │   ├─ Score via Claude API directly (subprocess: hermes ai)
  │   ├─ Filter: Keep ≥threshold (default 60)
  │   └─ Send via `hermes send --to telegram` (ONE message per item)
  └─ Exit 0 on success, 1 on fatal error

Cron Job (orchestration only)
  └─ No Agent involved. Script handles scraping, scoring, filtering, delivery.
```

**When to use:** You need per-search-term limits (different max-messages per search). Script does all work; cron just triggers. Direct API calls for scoring avoids Agent overhead.

## Procedure

**Choose your pattern before starting:** See Architecture section above. This procedure assumes Pattern A (Agent-driven). For Pattern B (direct script delivery), see references/direct-script-delivery.md.

### Step 1: Design Scraper Output

Decide what to extract from each item:
- **Core**: title, URL to detail page, category
- **Context for AI**: description text, price, seller/store, condition
- **Visual**: image URL (product thumbnail, listing photo)
- **Metadata**: date posted, location, rating (if available)

Example NDJSON line (Cash Converters tools):
```json
{"search_term": "ingco", "context": "power and hand tool brand (yellow and brown)", "product": {"title": "Ingco Csi18538", "price": "R 929", "store": "Victory Park", "url": "https://...", "image_url": "https://...", "category": "Circular Saw"}}
```

**Lesson: Include image_url in every item.** Claude can see images; comparing product thumbnail + title + description vs. context is far more accurate than title + description alone. Omitting images or using placeholder URLs loses signal and increases false positives.

### Step 2: Write Python Scraper

Structure:
```python
# 1. Load search criteria (JSON file: [{"search_term": "...", "context": "..."}, ...])
# 2. For each criterion:
#    a. Scrape items (Playwright, requests, or API)
#    b. Extract fields (title, URL, image_url, etc.)
#    c. For EACH item, print NDJSON line to stdout
#       json.dumps({"search_term": ..., "context": ..., "item": {...}})
# 3. Errors → stderr (not stdout — keep stdout pure NDJSON)
# 4. Exit code: 0 if any items scraped, 1 if fatal error
```

**Pitfall: Output a single JSON array instead of NDJSON.** If scraper accumulates all items and outputs `[{item1}, {item2}, ...]` at the end, the agent receives the entire array as one block, not line-by-line. Hermes cron will still process it, but Claude may try to analyze all items in one turn and batch messages. Output `{item1}\n{item2}\n` instead.

**Pitfall: Include verbose logging or timestamps in stdout.** Anything not valid JSON on each line breaks the NDJSON parser. Redirect all progress logging to stderr.

### Step 3: Create Criteria File

`~/.hermes/scripts/<project>/data/search_criteria.json`:
```json
[
  {
    "search_term": "brand-or-keyword",
    "context": "What you're looking for: brand X, quality Y, price range Z, condition C"
  }
]
```

**Lesson: Specificity of context matters.** Vague contexts ("tools") give Claude little signal. Precise contexts ("Ingco power drills, 20V, functional, under 1000 ZAR") let Claude score confidently. A weak context means low scores across the board or high false-positive threshold to get any matches.

### Step 4: Create Run Script

`~/.hermes/scripts/<project>/run.sh`:
```bash
#!/bin/bash
export PYTHONPATH="...site-packages:$PYTHONPATH"
cd /path/to/scripts/<project>
python3 orchestrator.py "$@"
```

Ensures Playwright and dependencies are on the path (cron environment is minimal).

### Step 5: Create Cron Job with Analysis Prompt

```bash
hermes cron create \
  "every day at 09:00" \
  "<PROMPT>" \
  --name="<project>-daily-hunt" \
  --script="<project>/run.sh" \
  --deliver="telegram"
```

**Prompt structure** (critical for per-item delivery):
```
1. For EACH line from script output (NDJSON):
   a. Parse JSON: extract search_term, context, item
   b. Analyze: score 0-100 (title + description + image vs context)
   c. Filter: if score < 60, skip silently
   d. Format: markdown (title, link, image, price, confidence, reason)
   e. Send ONE message (Telegram, email, Discord) for THIS item ONLY
   f. Move to next line
2. Do NOT batch multiple items into one message
3. Do NOT wait to collect matches — send as you process
4. If no items match, send one summary message
```

**Pitfall: Prompt tells agent to "analyze all products then send".** This encourages batching. The prompt MUST say "for EACH product" and "send ONE message per match". Sequence matters — encode delivery timing, not output shape.

**Pitfall: Cron `--deliver=telegram` batches all output into ONE message by default.** Agent formats output correctly but cron gateway bundles it. Use `---` block separators (see Step 5) to split into N messages, one per item.

**Pitfall: Use `--deliver=local` to test.** Local delivery prints to stdout, mixing with potential scraper output. Use `--deliver=telegram` or `--deliver=discord` with a test channel, or use Pattern B (direct script, `--no-agent` mode) to verify scraper output first.

### Step 6: Test Scraper Output (Before Cron)

```bash
cd ~/.hermes/scripts/<project>
bash run.sh 2>/dev/null | head -5 | jq .
```

Verify:
- Each line is valid JSON ✓
- `search_term`, `context`, `item` fields present ✓
- `item` contains `title`, `url`, `image_url`, description ✓

### Step 7: Dry-Run Cron Job

```bash
hermes cron run <job-id>
```

Check:
- Script ran without error ✓
- Hermes session created (visible in `hermes sessions list`) ✓
- If using Telegram: check bot received messages ✓

### Step 8: Verify Delivery Platform

Before scheduling, confirm the delivery target works:
```bash
# Telegram
hermes send --list telegram
echo "Test message" | hermes send --to telegram

# Discord
hermes send --list discord
echo "Test message" | hermes send --to discord:#channel

# Email
echo "Test message" | hermes send --to email:user@example.com
```

**Pitfall: Cron job created with `--deliver=telegram` but no Telegram bot configured.** The job will run, the agent will process items, but delivery will fail silently or error. Test the delivery channel before scheduling the job.

### Step 9: Schedule & Monitor

Job runs automatically on schedule. Monitor:
```bash
hermes cron list                    # Check next_run and last_run_at
hermes cron run <job-id>            # Manual trigger
hermes logs | grep <project>        # Errors (if any)
```

Adjust if needed:
- Lower confidence threshold (60 → 50) for more matches
- Refine context in `search_criteria.json` for better accuracy
- Add more search terms
- Change schedule: `hermes cron update <job-id> --schedule="every 6h"`

## Decision Points

### Image availability?

| Scenario | Action |
|----------|--------|
| Product site has thumbnail CDN URLs | Extract `<img src>` and include in `image_url` field |
| Site lazy-loads images (JS only) | Playwright `page.screenshot()` per item or use headless rendering |
| No images available | Omit `image_url` field; Claude will analyze title + description only (lower accuracy) |
| Images need local caching | Save to `data/image_cache/` with hash keys; pass cache URLs not CDN URLs |

### Confidence threshold?

Start with 60 (≥60 confidence scores). Tune based on results:
- Too many false positives → raise to 70 or 75
- Missing obvious matches → lower to 50 (but verify Claude's scoring in logs)
- If threshold varies by search term → embed it in `search_criteria.json`: `{"search_term": "...", "context": "...", "min_score": 65}`

### Delivery frequency?

- Daily (default): captures new listings, minimal redundancy
- Multiple times per day: good for fast-moving inventory (job boards, flash sales)
- Weekly: sufficient for slow inventory (rental properties, used cars)
- Per-script-run: use `--continuity` flag to dedupe against previous run's output

### Deduplication?

Three patterns:

1. **No dedup** (simple): send every match, even if scraped yesterday. User filters manually.
2. **URL log** (simple): save product URLs to `sent_products.txt`; agent skips if URL in log.
3. **Continuity mode** (advanced): `hermes cron update <job-id> --continuity`. Each run wakes up with previous output injected; agent dedupes automatically.

## Pitfalls

**Pitfall: Scraper extracts relative URLs without domain.** Image URLs like `/media/...` or product URLs like `/shop/product/123` will fail when sent to Telegram (404). Always construct absolute URLs: `f"https://domain.com{relative_url}"` or extract full URLs from HTML attributes.

**Pitfall: Scraper times out on first page load.** Playwright headless browsers are slow. If wait time > 10s per search, consider:
- Pre-warm the browser (keep one instance open, reuse)
- Use HTTP requests + regex if site is static (faster than headless)
- Parallelize searches (async)
- Increase cron job timeout (default 3 min); use `hermes cron update <job-id> --script-timeout=600`

**Pitfall: Search results page structure changes.** CSS selectors like `article:nth-child(1)` are brittle. If site updates, selector fails and scraper returns 0 items. Fallback:
- Use generic selectors: `article`, `div.product-card`, etc.
- Log HTML snippets on extraction failure for debugging
- Store page snapshots to `data/debug_screenshots/` on error
- Set cron job `--paused-reason="HTML structure changed—manual revalidation needed"` when first failure detected

**Pitfall: Image URLs expire or redirect after a few hours.** If product image URL is a temporary CDN link, embedding it in Telegram message hours later results in 404. Cache images locally:
```python
import hashlib
img_hash = hashlib.md5(img_url.encode()).hexdigest()
cached_path = f"data/image_cache/{img_hash}.webp"
if not Path(cached_path).exists():
    # Download and save
return cached_path  # Use local path in NDJSON
```
Then in Telegram message: embed local path with `![](file:///abs/path)` or upload via Hermes bot.

**Pitfall: Telegram message formatting breaks on special characters.** Product titles may contain `"`, `*`, `[`, `]`, backticks. Use Telegram's markdown escaping or switch to HTML mode. Example:
```python
import html
title_safe = html.escape(title)  # For HTML mode
# Or use raw title in markdown if only ** _ ` are used
```

## Examples

### Example 1: Cash Converters Tools (Secondhand Retail)
See related skill `cash-converters-automation` for a complete working implementation.

### Example 2: Job Board Daily Digest

Search terms + contexts:
```json
[
  {"search_term": "python engineer", "context": "Remote, senior level, fintech stack"},
  {"search_term": "devops", "context": "AWS/Kubernetes, contract 3-6 months"}
]
```

Scraper extracts: job title, company, URL, salary, location, posting date, job description snippet.

Agent scores each job: does it match the context (remote + fintech + senior)?

Matches delivered to Telegram one per message.

### Example 3: Apartment Rental Monitor

Search: apartment rentals in a city by price range.

Scraper extracts: address, rent, bedrooms, photo, link to listing.

Agent scores: does it fit budget, location, size requirements?

Matches emailed daily as a digest (one email per matched apartment).

## Troubleshooting

**Cron job reports 'succeeded' but no messages received:**
- Verify delivery platform: `hermes send --list telegram` shows a target ✓
- Check if agent received any items: `hermes cron run <job-id>` then search logs for "Received N products"
- If scraper returned 0 items: search term may not exist on site, or scraper has stale CSS selectors
- If agent received items but didn't send: confidence scores all < threshold, or agent encountered an error (check logs)

**"NDJSON parse error" or messages arriving out of order:**
- Verify scraper stdout is pure JSON lines: `bash run.sh 2>/dev/null | head -3 | od -c` (check for extra whitespace, debug output)
- Redirect logging to stderr: `print("message", file=sys.stderr)`
- If using custom parser, ensure it reads line-by-line and does not buffer

**Too many false positives (low-confidence matches being sent):**
- Raise confidence threshold in prompt: change "≥60" to "≥70"
- Refine search context: instead of "tools", use "Ingco 20V cordless drills, functional, under 1000 ZAR"
- Review Claude's scoring in logs to understand what it's counting as a match

**Scraper runs slow or times out:**
- Use `asyncio` for parallel searches (Playwright supports async)
- Pre-warm browser instance; do not create new browser for each search
- Increase cron timeout via `hermes cron update <job-id> --script-timeout=600` (10 min)
- For HTTP scraping, use `aiohttp` or `httpx` instead of Playwright headless

## Lessons Encoded

- **NDJSON line-by-line is key to per-item delivery**: one message per match, not batched.
- **Image URLs as analysis input**: include product thumbnails so Claude sees visual context.
- **Specificity of context**: vague criteria ("tools") fail; precise criteria ("Ingco 20V cordless drills under 1000 ZAR") succeed.
- **Absolute URLs in output**: relative URLs fail when delivered to Telegram.
- **Scraper robustness**: brittle CSS selectors, expired CDN URLs, and site structure changes all break the pipeline silently.
- **Per-search-term limits require explicit tracking**: if different search terms should each have a 20-message budget (not 20 total), track sent count as a dict keyed by search_term, not a global counter.
- **Price extraction from split DOM**: numeric values with spaces ("R 1 299") often span multiple HTML elements. Regex must include spaces (`[\d\s,]+`) then strip them post-extraction. See references/dom-extraction-pitfalls.md for other common extraction mistakes (relative URLs, brittle selectors, expired image CDNs, etc.).

## See Also

- `references/direct-script-delivery.md` — Use Pattern B when you need per-search-term limits or direct Telegram control without Agent overhead.
- `references/dom-extraction-pitfalls.md` — Common HTML parsing mistakes and fixes: price splits, relative URLs, brittle selectors, JS-rendered content, whitespace handling.

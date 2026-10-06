# Persistent Ledger Pattern for Deduplication

When a cron job needs to track what it has already delivered (to avoid resending the same item or to detect updates), use a persistent ledger file.

## Three-Category Classification

Every incoming item is classified into one of three categories:

### NEW
- **Condition:** Item identifier not present in ledger
- **Action:** Include in output/delivery
- **Ledger update:** Add entry with current timestamp
- **Example:** First time seeing product ID 15485113 → send to Telegram

### UPDATED (aka PRICE_CHANGE)
- **Condition:** Item identifier in ledger AND at least one tracked field differs
- **Action:** Include in output (optionally flag as "PRICE UPDATE" or similar)
- **Ledger update:** Overwrite the differing field(s) and timestamp
- **Example:** Product ID 15485113 exists in ledger at price "R 2999" but current price is "R 1999" → send as PRICE_CHANGE

### DUPLICATE
- **Condition:** Item identifier in ledger AND all tracked fields are identical
- **Action:** Silently skip (no output, no Telegram message)
- **Ledger update:** None
- **Example:** Product ID 15485113 exists in ledger at price "R 2999" and current price is still "R 2999" → do not send

## Ledger File Structure

**Shape:** JSON object keyed by item identifier (string):

```json
{
  "item_id_1": {
    "id": "item_id_1",
    "title": "Item Title",
    "price": "R 1000",
    "url": "https://example.com",
    "sent_at": "2026-10-06T09:01:35.000000",
    "source_term": "search_term"
  },
  "item_id_2": { ... }
}
```

**Key fields:**
- **id** (string): Unique identifier for the item (must be consistent across runs — if item id changes, dedup breaks)
- **title, price, url** (strings): Tracked fields used for UPDATE detection. Compare these byte-for-byte.
- **sent_at** (ISO 8601 timestamp string): When this item was last delivered. Used for cleanup (remove entries >90 days old).
- **source_term** (string or array): Which search term/filter matched this item (for audit trail).

## Read-Merge-Write Pattern

Agent or script updates ledger in three steps:

```python
# 1. READ
with open(ledger_path, 'r') as f:
    ledger = json.load(f)

# 2. MERGE (for each NEW/UPDATED item, add/overwrite entry)
for item in items_to_send:
    ledger[item['id']] = {
        'id': item['id'],
        'title': item['title'],
        'price': item['price'],
        'url': item['url'],
        'sent_at': datetime.utcnow().isoformat(),
        'source_term': item['source']
    }

# 3. WRITE (backup first, then overwrite)
shutil.copy(ledger_path, ledger_path + '.bak')
with open(ledger_path, 'w') as f:
    json.dump(ledger, f, indent=2)
```

This pattern is safe for single-agent scenarios (one Agent write per cron run, no concurrent access).

## Field Comparison

**Critical rule:** Fields are compared byte-for-byte, NOT semantically or numerically.

**Examples:**
- `"R 2999"` == `"R 2999"` → DUPLICATE (no update)
- `"R 2999"` vs `"R 1999"` → UPDATE (numeric difference)
- `"R 2999"` vs `"R2999"` (missing space) → UPDATE (byte difference, treated as different value)
- `"R 2 999"` vs `"R 2999"` (grouping space) → UPDATE (byte difference)

**Lesson:** Scraper must normalize field format (e.g., always `"R XXXX"` with no grouping, no extra spaces) to ensure consistent ledger comparison. If format drifts, the same item appears to change even though it hasn't.

## Cleanup Integration

Cleanup removes entries with `sent_at` > 90 days old (configurable). This prevents ledger from growing indefinitely but also:

- An item unseen for 91+ days will be removed from ledger
- If the item reappears later, it will be treated as NEW again
- This is intentional — refreshes tracking for long-stale items

Cleanup runs at job start, before scraping/comparison. This is safe because cleanup only removes old entries; it never removes entries that were just added.

## Testing: Reset Ledger for Full Scan

To test dedup logic and see all items as NEW:

```bash
# Clear ledger
echo '{}' > /path/to/ledger.json

# Optionally clear cache/results
rm -rf /path/to/cache/*
rm -rf /path/to/results/*

# Next job run will treat all items as NEW
```

After this, the next run will:
1. Scrape all items
2. Find no entries in empty ledger
3. Classify all as NEW
4. Send all matching items to Telegram/Slack/email
5. Populate ledger for future dedup

## Common Pitfalls

**Pitfall: Inconsistent Item ID Across Runs.** If your scraper generates item IDs differently on different runs (e.g., sometimes from product URL, sometimes from page position), the same item gets different IDs. Ledger dedup fails — same item appears twice. **Fix:** ID must be deterministic and stable. Extract from a unique, unchanging field (e.g., product database ID, not URL position).

**Pitfall: Format Drift in Tracked Fields.** If the scraper changes how it formats price ("R 2999" → "R2999"), the same item appears to have changed price, triggering UPDATE even though nothing changed. **Fix:** Normalize format in scraper (strip spaces, consistent casing, etc.). Test by running scraper twice and comparing output — fields should be byte-identical for same products.

**Pitfall: Updating Ledger Before Filtering.** If you update ledger for ALL items (including low-confidence/non-matching ones), you lose the ability to resend items later if filtering rules change. **Fix:** Update ledger ONLY for items that pass all filters and will be delivered. Items that don't match should not appear in ledger.

**Pitfall: No Backup Before Write.** If a write fails partway (disk full, permission error), the ledger file is corrupted. **Fix:** Always backup before write: `shutil.copy(old_path, old_path + '.bak')` before the actual write.

**Pitfall: Concurrent Writes.** If multiple agents or jobs try to update the same ledger file simultaneously, writes can corrupt the JSON. **Fix:** Single cron job = single agent = single write per run. No coordination needed. If you need multi-agent access, add file locking or use a database.

## Extensions

### Track Multiple Fields
If you want to detect changes beyond price (e.g., stock status, description), add them to tracked fields:

```python
ledger[item['id']] = {
    'title': item['title'],
    'price': item['price'],
    'status': item['status'],  # in stock / sold
    'sent_at': utcnow()
}
```

Comparison then checks all of them. Update triggers if ANY field changes.

### Store Delivery Metadata
Optionally track what was sent:

```python
ledger[item['id']] = {
    ...,
    'delivered_count': 1,
    'delivery_channels': ['telegram'],  # add more if resend via email, etc.
    'last_update_reason': 'price_change'  # for audit
}
```

This is optional; ledger only needs id + tracked fields + sent_at for dedup + cleanup.

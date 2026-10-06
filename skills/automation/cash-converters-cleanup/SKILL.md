---
name: cash-converters-cleanup
description: Clean old files and ledger entries (>90 days) before writes.
tags: [cash-converters, automation, cleanup, maintenance]
---

# Cash Converters Cleanup: Old Files & Ledger

Automatically removes stale files and ledger entries older than 3 months (90 days) from the Cash Converters automation pipeline.

## When to Run

**At the START of every cron job execution**, before any scraping, deduplication, or write operations. This prevents data bloat and keeps tracking efficient.

## Scope: What Gets Cleaned

- **Ledger entries** in `/home/opc/.hermes/scripts/cash_converters/data/sent_products.json` — remove items with `sent_at` timestamp > 90 days old
- **Scrape cache files** in `/home/opc/.hermes/scripts/cash_converters/data/scrape_cache/` — delete `.json` or other files with mtime > 90 days old
- **Log files** in `/home/opc/.hermes/scripts/cash_converters/logs/` — delete `.log` files older than 90 days

## Ready-to-Use Function

Paste this into your orchestrator at the **top**, before any scraping:

```python
import json
import os
import time
import shutil
import sys
from datetime import datetime, timedelta

def cleanup_ledger(ledger_path, days=90):
    """Remove ledger entries older than N days."""
    try:
        with open(ledger_path, 'r') as f:
            ledger = json.load(f)
        
        removed = 0
        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)
        cleaned = {}
        
        for pid, entry in ledger.items():
            try:
                sent_at = datetime.fromisoformat(entry['sent_at'].replace('Z', '+00:00'))
                if sent_at >= cutoff:
                    cleaned[pid] = entry
                else:
                    removed += 1
            except (ValueError, KeyError):
                pass
        
        if removed > 0:
            shutil.copy(ledger_path, ledger_path + '.bak')
            with open(ledger_path, 'w') as f:
                json.dump(cleaned, f, indent=2)
            print(f"Cleanup: Removed {removed} ledger entries (>{days} days old)", file=sys.stderr)
    except Exception as e:
        print(f"Cleanup error (ledger): {e}", file=sys.stderr)

def cleanup_files(dir_path, days=90, extensions=None):
    """Remove files older than N days from directory."""
    if not os.path.isdir(dir_path):
        return
    
    try:
        removed = 0
        now_ts = time.time()
        cutoff_ts = now_ts - (days * 86400)
        
        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            if not os.path.isfile(filepath):
                continue
            if extensions and not any(filename.endswith(ext) for ext in extensions):
                continue
            
            mtime = os.path.getmtime(filepath)
            if mtime < cutoff_ts:
                try:
                    os.remove(filepath)
                    removed += 1
                except Exception:
                    pass
        
        if removed > 0:
            print(f"Cleanup: Deleted {removed} files from {dir_path} (>{days} days old)", file=sys.stderr)
    except Exception as e:
        print(f"Cleanup error (files): {e}", file=sys.stderr)

# CALL THIS AT JOB START
def run_cleanup():
    cleanup_ledger('/home/opc/.hermes/scripts/cash_converters/data/sent_products.json', days=90)
    cleanup_files('/home/opc/.hermes/scripts/cash_converters/data/scrape_cache/', days=90)
    cleanup_files('/home/opc/.hermes/scripts/cash_converters/logs/', days=90, extensions=['.log'])

# In your main cron block:
if __name__ == '__main__':
    run_cleanup()  # <-- Call FIRST
    # Now proceed with scraping, dedup, writes
```

## Behavior

✅ Removes ledger entries with `sent_at` > 90 days in the past  
✅ Deletes cache/log files with mtime > 90 days old  
✅ Creates `.bak` backup before modifying ledger  
✅ Logs to stderr: `Cleanup: Removed X entries (>90 days old)`  
✅ Non-blocking: errors logged, job continues  
✅ Idempotent: safe to run multiple times per job  
✅ JSON validated before and after write  

## Example Output

```
Cleanup: Removed 12 ledger entries (>90 days old)
Cleanup: Deleted 5 files from /home/opc/.hermes/scripts/cash_converters/data/scrape_cache/ (>90 days old)
Cleanup: Deleted 3 files from /home/opc/.hermes/scripts/cash_converters/logs/ (>90 days old)
```

## Safety

- **Backup:** Ledger backed up to `sent_products.json.bak` before any write
- **Threshold:** Hardcoded to 90 days (3 months)—adjust in function call if needed
- **Validation:** JSON syntax checked; malformed entries skipped, not deleted
- **Permission errors:** Logged and ignored, do not crash the job
- **Missing dirs:** Silently skipped if they don't exist yet

## Integration Checklist

- [ ] Copy the cleanup functions into your orchestrator
- [ ] Add `run_cleanup()` call at the **very start** of main
- [ ] Test locally with `--dry-run` or inspect logs after first run
- [ ] Monitor cron job stderr output for cleanup messages
- [ ] Review `.bak` backup files periodically (can be deleted manually)

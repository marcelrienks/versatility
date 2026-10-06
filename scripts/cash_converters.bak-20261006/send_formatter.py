#!/usr/bin/env python3
"""Cash Converters Telegram Sender — Layer 3 (dedup + format + emit).

Reads matches queued by the cron Agent (Layer 2) in data/pending_matches.jsonl,
deduplicates against the sent_products.json ledger, and prints one "---"
-delimited text block per NEW/PRICE_CHANGE product to stdout.

This script is run by a `no_agent` cron job. Its stdout is handed verbatim to
the live Telegram adapter by the cron scheduler, which (via a local patch,
_split_products_with_images in plugins/platforms/telegram/adapter.py) splits
on the literal "\n---\n" separator and sends each block as its own Telegram
message. See README.md for why this indirection exists (short version:
TELEGRAM_BOT_TOKEN can never reach a cron script subprocess, so this script
cannot call the Telegram API itself — it can only produce text for the
gateway, which holds the real token, to deliver).

No LLM, no network calls beyond what scraping already did upstream. Pure
dedup + text formatting.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
PENDING_FILE = DATA_DIR / "pending_matches.jsonl"
LEDGER_FILE = DATA_DIR / "sent_products.json"


def load_pending() -> List[Dict[str, Any]]:
    """Read and parse data/pending_matches.jsonl (written by the cron Agent)."""
    if not PENDING_FILE.exists():
        return []
    entries = []
    for line in PENDING_FILE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"Skipping malformed pending line: {e}", file=sys.stderr)
    return entries


def load_ledger() -> Dict[str, Dict[str, Any]]:
    """Read the dedup ledger: product_id -> {price, sent_at, title}."""
    if not LEDGER_FILE.exists():
        return {}
    try:
        return json.loads(LEDGER_FILE.read_text())
    except Exception as e:
        print(f"Warning: could not load ledger, starting fresh: {e}", file=sys.stderr)
        return {}


def save_ledger(ledger: Dict[str, Dict[str, Any]]) -> None:
    LEDGER_FILE.write_text(json.dumps(ledger, indent=2))


def classify(entry: Dict[str, Any], ledger: Dict[str, Dict[str, Any]]) -> Tuple[str, Optional[str]]:
    """Return (status, previous_price). status is one of NEW, PRICE_CHANGE, DUPLICATE."""
    product_id = str(entry.get("product_id") or "").strip()
    current_price = entry.get("price", "")

    if not product_id:
        # No stable id to dedup against — treat as NEW every time (can't do better).
        return "NEW", None

    prev = ledger.get(product_id)
    if prev is None:
        return "NEW", None

    prev_price = prev.get("price", "")
    if prev_price and current_price and prev_price != current_price:
        return "PRICE_CHANGE", prev_price

    return "DUPLICATE", None


def format_block(entry: Dict[str, Any], status: str, previous_price: Optional[str]) -> str:
    """One "---"-delimited-ready text block (caller joins blocks with the separator)."""
    title = entry.get("title") or "Unknown product"
    url = entry.get("url", "")
    price = entry.get("price", "")
    store = entry.get("store", "")
    score = entry.get("score", "?")

    lines = []
    if status == "PRICE_CHANGE":
        lines.append("\U0001f514 PRICE UPDATE")
    lines.append(title)
    lines.append(url)
    if status == "PRICE_CHANGE":
        lines.append(f"Previous: {previous_price} -> NEW: {price} | {store}")
    else:
        lines.append(f"{price} | {store}")
    lines.append(f"Confidence: {score}/100")
    return "\n".join(lines)


def main() -> int:
    pending = load_pending()
    if not pending:
        print("No pending matches, nothing to send", file=sys.stderr)
        return 0

    ledger = load_ledger()
    blocks = []
    sent_count = 0
    duplicate_count = 0
    price_change_count = 0

    for entry in pending:
        status, previous_price = classify(entry, ledger)

        if status == "DUPLICATE":
            duplicate_count += 1
            continue

        blocks.append(format_block(entry, status, previous_price))
        sent_count += 1
        if status == "PRICE_CHANGE":
            price_change_count += 1

        product_id = str(entry.get("product_id") or "").strip()
        if product_id:
            ledger[product_id] = {
                "price": entry.get("price", ""),
                "title": entry.get("title", ""),
                "sent_at": datetime.now().isoformat(),
            }

    save_ledger(ledger)
    PENDING_FILE.unlink(missing_ok=True)

    print(
        f"Sent {sent_count} ({price_change_count} price changes), "
        f"{duplicate_count} duplicates skipped",
        file=sys.stderr,
    )

    if blocks:
        # Blocks separated by a line containing exactly "---" — this is the
        # literal delimiter the Telegram adapter's product-splitter looks for.
        print("\n\n---\n\n".join(blocks))

    return 0


if __name__ == "__main__":
    sys.exit(main())

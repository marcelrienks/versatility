# Direct Script Delivery Pattern (No Agent)

## When to Use

- You need per-search-term limits (each search gets 20 messages, not 20 total)
- Filtering logic is simple or rule-based (can be hard-coded)
- You want to avoid Agent overhead and latency
- Telegram delivery must be immediate (no Agent batching)

## Architecture

```
Python Script (all-in-one)
├─ Scrape products from target site
├─ For EACH product:
│  ├─ Call Claude API directly (subprocess: `hermes ai "prompt"`)
│  ├─ Parse score 0-100
│  ├─ Check limit for this search term (dict-tracked)
│  ├─ Send via `hermes send --to telegram` if score ≥ threshold
│  └─ Increment counter for this search term
└─ Exit 0 (all sent) or 1 (fatal error)

Cron Job
└─ Runs script, waits for completion, no Agent involved
```

## Implementation Steps

### Step 1: Track Per-Search-Term Limits

```python
from collections import defaultdict

class ProductHunter:
    def __init__(self):
        self.max_per_search = 20  # Per-search limit
        self.sent_per_search = defaultdict(int)  # Track by search term
        self.total_sent = 0
        
    def can_send(self, search_term: str) -> bool:
        """Check if this search term has messages left."""
        return self.sent_per_search[search_term] < self.max_per_search
        
    def record_sent(self, search_term: str):
        """Increment counter after successful send."""
        self.sent_per_search[search_term] += 1
        self.total_sent += 1
```

### Step 2: Score via Claude Subprocess

```python
import subprocess
import json

def score_product(product: dict, search_term: str, context: str) -> int:
    """Call Claude to score product against context. Returns 0-100."""
    prompt = f"""
Product: {product.get('title')}
Store: {product.get('store')}
Price: {product.get('price')}

Context: {context}

Does this product match the context? Score 0-100 (0=no match, 100=perfect match).
Respond with ONLY the number, nothing else.
"""
    
    try:
        result = subprocess.run(
            ['hermes', 'ai', prompt],
            capture_output=True,
            text=True,
            timeout=10
        )
        score_str = result.stdout.strip()
        return int(score_str)
    except Exception as e:
        print(f"[-] Scoring error: {e}", file=sys.stderr)
        return 0  # Fail-safe: score 0 if error
```

### Step 3: Send via hermes send

```python
import subprocess

def send_telegram(message: str) -> bool:
    """Send message to Telegram via Hermes. Returns True on success."""
    try:
        result = subprocess.run(
            ['hermes', 'send', '--to', 'telegram', message],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[!] Send error: {e}", file=sys.stderr)
        return False
```

### Step 4: Main Loop

```python
async def hunt_and_send(search_criteria: list) -> dict:
    """Scrape, score, filter, send per-search-term."""
    hunter = ProductHunter()
    results = {"sent": 0, "skipped": 0, "per_search": {}}
    
    for criterion in search_criteria:
        search_term = criterion['search_term']
        context = criterion['context']
        results["per_search"][search_term] = 0
        
        # Scrape products for this search term
        products = await scrape(search_term)
        
        for product in products:
            # Check search-term limit
            if not hunter.can_send(search_term):
                print(f"[-] Limit reached for '{search_term}'", file=sys.stderr)
                results["skipped"] += 1
                continue
            
            # Score product
            score = score_product(product, search_term, context)
            
            if score >= 60:  # Threshold
                # Format message
                msg = f"""
{product['title']}
{product['url']}
{product['price']} | {product['store']}
Confidence: {score}/100
"""
                
                # Send
                if send_telegram(msg):
                    hunter.record_sent(search_term)
                    results["sent"] += 1
                    results["per_search"][search_term] += 1
                    print(f"[+] Sent: {product['title'][:40]} ({hunter.sent_per_search[search_term]}/{hunter.max_per_search} for '{search_term}')", file=sys.stderr)
                else:
                    results["skipped"] += 1
                    print(f"[!] Failed to send: {product['title'][:40]}", file=sys.stderr)
            else:
                results["skipped"] += 1
                print(f"[-] Low confidence ({score}/100): {product['title'][:40]}", file=sys.stderr)
    
    return results
```

### Step 5: Cron Job (No Agent Mode)

```bash
hermes cron create \
  "every day at 09:00" \
  --name="Product Hunt Daily" \
  --script="~/.hermes/scripts/hunt_and_send.py" \
  --no-agent
```

No `--deliver` flag (script handles it). No prompt (script is standalone).

Verify:
```bash
hermes cron list
hermes cron run <job-id>  # Test manually
hermes cron history <job-id>  # Check logs
```

## Pitfalls

**Pitfall: Script calls `hermes send` but cron environment lacks hermes CLI.** Cron runs in a constrained shell. Ensure:
```bash
# In run.sh or script
export PATH="~/.hermes/bin:$PATH"
which hermes || { echo "Hermes not in PATH"; exit 1; }
```

**Pitfall: Subprocess timeout waiting for Claude response.** If `hermes ai` is slow, script blocks. Use longer timeout or async:
```python
try:
    result = subprocess.run(..., timeout=30)  # 30s for Claude
except subprocess.TimeoutExpired:
    return 0  # Score 0 on timeout, don't crash
```

**Pitfall: Per-search counter initialized but reset on each run.** If you want to avoid resending the same product across multiple days, track sent URLs in a file:
```python
import json
from pathlib import Path

SENT_FILE = Path("data/sent_urls.json")

def load_sent_urls() -> set:
    if SENT_FILE.exists():
        with open(SENT_FILE) as f:
            return set(json.load(f))
    return set()

def save_sent_urls(urls: set):
    with open(SENT_FILE, 'w') as f:
        json.dump(list(urls), f)

# In loop:
if product['url'] in sent_urls:
    continue  # Already sent this URL
```

**Pitfall: Multiple runs per day (e.g., every 6h) accumulate messages.** Each run starts fresh and sends up to 20 per search term again. If you want to dedupe across runs, track sent URLs (see above). Alternatively, increase search criteria context precision to reduce false positives on repeated scrapes.

## Comparison: Pattern A vs Pattern B

| Aspect | Agent-Driven (A) | Direct Script (B) |
|--------|------------------|-------------------|
| **Setup** | More code (Agent prompt) | More code (script logic) |
| **Per-search limits** | Harder (Agent needs per-item context) | Easy (dict tracking) |
| **Filtering complexity** | Excellent (Claude context-aware) | Good (rule-based) |
| **Latency** | Higher (Agent processing) | Lower (direct send) |
| **Fine-tuning** | Prompt-only (no deploy) | Code changes needed |
| **Scalability** | Limited by Agent throughput | Unlimited (subprocess calls) |
| **Image analysis** | Yes (Claude sees images) | No (script doesn't load images) |
| **Error recovery** | Agent retries; cron manages state | Script manages state |

## Example: Cash Converters

See working implementation in `~/.hermes/scripts/cash_converters/hunt_and_send.py`:
- 4 search terms (ingco, wera, wiha, gadore)
- 20 per search term (80 total max)
- Direct Telegram send via `hermes send --to telegram`
- Per-search tracking with `sent_per_search` dict
- Claude scoring via direct subprocess

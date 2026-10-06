# Cash Converters Daily Product Hunter

Automated daily product hunting on Cash Converters (South Africa). Scrapes products per
search term, has an LLM agent score/match them against your criteria, then sends one
Telegram message per matched product — fully automated via two chained Hermes cron jobs.

**Location:** `~/.hermes/scripts/cash_converters/`

## Architecture (3 layers, 2 cron jobs)

This project is split into three logical layers. Layers 1 and 3 are deterministic Python
scripts; Layer 2 must be an LLM agent (it does the actual judgment call). Layers 1 and 2
run inside one cron job (the agent can read a pre-run script's stdout); Layer 3 runs as a
second, separate `no_agent` cron job, because of two hard Hermes platform constraints
explained below.

```
Layer 1: SEARCH + SCRAPE + STORE            Layer 2: AGENT SCORE + MATCH + STORE
┌───────────────────────────┐               ┌──────────────────────────────────┐
│ orchestrator.py           │   NDJSON      │ Cron Job A (agent, deliver=local) │
│ - load search_criteria    │──(stdout,     │ - read NDJSON from script output  │
│   .json                   │   injected    │ - score 0-100 per product vs.     │
│ - per search term:        │   into the    │   its search context              │
│   scrape first N products │   agent       │ - keep score >= 60                │
│ - NO dedup here anymore    │   prompt)     │ - write_file: append matches to   │
│   (moved to Layer 3)       │               │   data/pending_matches.jsonl       │
└───────────────────────────┘               └──────────────────────────────────┘
                                                              │
                                                              │ shared file
                                                              ▼
                                             Layer 3: DEDUP + FORMAT + SEND
                                             ┌──────────────────────────────────┐
                                             │ Cron Job B (no_agent,            │
                                             │ deliver=telegram, +10 min after A)│
                                             │ send_formatter.py:                │
                                             │ - read pending_matches.jsonl      │
                                             │ - read data/sent_products.json    │
                                             │   ledger (product_id -> price)    │
                                             │ - DEDUP HERE: skip unchanged,     │
                                             │   flag price changes             │
                                             │ - print one "---"-delimited text  │
                                             │   block per NEW/PRICE_CHANGE      │
                                             │   product to stdout               │
                                             │ - update ledger, clear pending    │
                                             │   file                            │
                                             └──────────────────────────────────┘
                                                              │
                                                              ▼
                                             Hermes cron delivery (same code path
                                             for agent AND no_agent jobs) sends the
                                             job's stdout/final-response through the
                                             live Telegram adapter. The adapter has a
                                             product-splitter patch that explodes text
                                             on "\n---\n" into one Telegram message per
                                             block — this is what turns Layer 3's single
                                             stdout blob into individual messages.
```

### Why two cron jobs, and why Layer 3 is script-only

Two non-negotiable Hermes platform rules forced this shape (verified empirically, not
assumed — see "Platform constraints" below):

1. **`send_message` (the tool an agent would use to send a Telegram message itself) is
   unconditionally unavailable to every cron-spawned agent.** The `messaging` toolset is
   always stripped for cron jobs (loop-prevention, hardcoded in
   `cron/scheduler.py::_resolve_cron_disabled_toolsets`, not configurable per-job). So
   Layer 2 (the agent) can score and write files, but it can never directly deliver to
   Telegram.
2. **`TELEGRAM_BOT_TOKEN` can never reach any cron script subprocess.** It's a Tier-1
   secret, unconditionally stripped from every spawned child process
   (`tools/environments/local_env_policy.py::_ALWAYS_STRIP_KEYS`), with no
   `env_passthrough` override allowed (that bypass is explicitly blocked, see
   GHSA-rhgp-j443-p4rf). So Layer 3 (a script) can never call the Telegram Bot API
   directly either.

The only way text reaches Telegram from a cron job — agent or `no_agent` — is the
**job's own delivery pipeline**: whatever the job's final stdout (no_agent) or final
response (agent) is, the cron scheduler hands it to the live gateway process (which is
the only thing holding the real bot token) and that gateway's Telegram adapter sends it.

That delivery path has one more, non-standard twist this project relies on: **the
Telegram adapter itself has been hand-patched** (`_split_products_with_images()` /
`_send_product_messages()` in `plugins/platforms/telegram/adapter.py`) to split
delivered text on the literal substring `\n---\n` and send each resulting section as its
own separate Telegram message (with its image, if a markdown image is embedded in that
section). This is NOT a standard/documented Hermes feature — it's a local patch to the
Telegram adapter — but it's real, it's live, and it applies identically whether the
content came from an agent's final response OR a `no_agent` script's stdout (both route
through the same `_deliver_to_platform` → `adapter.send()` call). This was verified live:
a `no_agent` test job printing two `---`-delimited blocks to stdout produced the log line
`[Telegram] Split content into 2 product sections` and two separate Telegram messages.

**Practical consequence:** Layer 3 must be the one that emits the final `---`-delimited
text, since it's the layer closest to delivery and (per your call) the one that owns
dedup. Doing dedup in Layer 3 instead of Layer 1 means Layer 1 can stay simple/stateless
(scrape and emit everything, every run), and the one ledger file
(`data/sent_products.json`) only has to be read/written by one process.

### Platform constraints — how these were confirmed (for future maintainers)

Don't take the above as received wisdom — re-verify if you upgrade Hermes or this breaks:

- `grep -n "there is deliberately no agent-callable send_message tool" toolsets.py` and
  `cron/scheduler.py::_resolve_cron_disabled_toolsets` (always disables `messaging`,
  `clarify`, and — unless `cron.allow_agent_scheduling` — `cronjob`, for every cron run).
- `tools/environments/local_env_policy.py::_ALWAYS_STRIP_KEYS` includes
  `TELEGRAM_BOT_TOKEN`; `tools/env_passthrough.py::_is_hermes_provider_credential` refuses
  to ever re-allow a blocklisted name via `terminal.env_passthrough` in config.yaml.

### Two delivery send paths, and a config wrapper that broke both (fixed 2026-10-06)

Cron delivery is NOT a single code path. `cron/scheduler_delivery.py::_deliver_result` tries
the **live adapter** first (`_deliver_via_live_adapter` → `TelegramAdapter.send()`, which has
the `_split_products_with_images` patch) and falls back to a **standalone** one-shot sender
(`_deliver_standalone` → `tools/send_message_tool.py::_send_to_platform` →
`tools/send_message_senders.py::_send_telegram`) whenever the live adapter/gateway loop isn't
reachable — e.g. most manual `cronjob(action='run')` triggers from a desktop/CLI session.
**Only the live-adapter path originally had the `---`-splitter.** The standalone sender was a
bare `python-telegram-bot` call with no splitting at all, so manual test runs silently sent one
giant combined message while a real scheduled 09:00/09:10 tick (which usually has a live
adapter) might have worked. **Fixed by adding the same `\n---\n`-splitting logic to
`_send_telegram` in `tools/send_message_senders.py`** (see `_split_telegram_product_sections`
there) — both code paths now split identically.

Separately, **`cron.wrap_response` (config.yaml, default `true`) wraps every delivered cron
body** with a header (`Cronjob Response: <name>\n(job_id: ...)\n-------------\n\n`) and a
footer ("To stop or manage this job..."). That header's own `-------------` (13 dashes) and
the footer text corrupt the clean `\n---\n` boundaries Layer 3 emits, breaking the splitter
regardless of which send path handles it. **This project needs `cron.wrap_response: false`
globally** (`hermes config set cron.wrap_response false`) — there's no per-job override.

If per-product splitting breaks again after a Hermes update, check BOTH of these before
anything else:
1. `hermes config get cron.wrap_response` — must be `false`.
2. Does `tools/send_message_senders.py::_send_telegram` still contain
   `_split_telegram_product_sections` and call it? (A Hermes update could overwrite this file.)

### Gotcha: a long-lived `hermes serve` process caches old code in memory

If you edit the Telegram adapter or `send_message_senders.py` and test changes don't seem to
take effect — not even after `hermes gateway restart` — check for a separate, older `hermes
serve --isolated ...` process (`ps aux | grep "hermes serve"`). The **desktop app's own chat
session runs through this `serve` backend, not the messaging `gateway run` process** (they are
separate, per the main Hermes docs: `serve` is control-plane/desktop-spawned, `gateway run`
is the long-lived messaging daemon). A `serve` process that predates your code edit keeps
stale in-memory module objects no matter how many times you restart the *other* process or
rewrite files on disk. If manual `cronjob(action='run')` tests from a desktop chat don't
reflect a code change, find and restart (or kill — it respawns) the `serve` PID, not just
`gateway run`.

- `cron/scheduler_delivery.py::_live_send_text` / `_standalone_send` is the pair of send
  lanes described above; both ultimately reach `adapter.send()`'s Telegram equivalent one way
  or another.


## File Structure

```
~/.hermes/scripts/cash_converters/
├── run_scrape.sh                # Job A entry point: scrape + prep for agent
├── orchestrator.py              # Layer 1: scrape per search term, output NDJSON (no dedup)
├── scraper.py                   # Playwright browser automation (used by orchestrator.py)
├── config.py                    # Shared configuration (paths, selectors, timeouts)
├── run_send.sh                  # Job B entry point: dedup + format + emit for delivery
├── send_formatter.py            # Layer 3: dedup, format "---"-delimited blocks, print to stdout
├── requirements.txt              # Python dependencies (playwright)
├── README.md                     # This file
└── data/
    ├── search_criteria.json      # Your watchlist (EDIT THIS)
    ├── pending_matches.jsonl     # Layer 2 -> Layer 3 handoff (ephemeral; cleared each Job B run)
    ├── sent_products.json        # Layer 3's dedup ledger (product_id -> last sent price)
    └── results/                  # Raw scrape archives (one per Job A run)
```

Legacy files removed by this rewrite: `run.sh` (replaced by `run_scrape.sh` /
`run_send.sh`), `analyze_products.py` (its pass-through logic is now redundant — the
agent reads the script's stdout directly via the cron job's `script` field).

## How It Works

### Job A — "Cash Converters Daily Hunt" (agent, `deliver=local`, 09:00 daily)

1. **Script phase (Layer 1):** `run_scrape.sh` runs `orchestrator.py`, which loads
   `data/search_criteria.json` and for each `{search_term, context}` entry scrapes the
   first N products via `scraper.py` (Playwright). Outputs NDJSON (one product JSON
   object per line) to stdout — no deduplication, every run emits everything found.
   Also archives the raw results to `data/results/results_<timestamp>.json`.
2. **Agent phase (Layer 2):** the cron scheduler injects that NDJSON into the agent's
   prompt as context. The agent must NOT use `execute_code`, `terminal`, or
   `send_message` (all blocked/unavailable in cron sessions — the prompt tells it so
   explicitly to avoid wasted blocked tool-call attempts). For each product line, it
   scores 0-100 against `search_term`/`context`; matches scoring >=60 get appended (via
   the `write_file` tool) to `data/pending_matches.jsonl` as one JSON object per line:
   `{"product_id", "title", "url", "price", "store", "image_url", "score"}`.
3. Delivery is `local` — nothing reaches Telegram from this job. Its final text response
   is just a one-line confirmation for the run log.

### Job B — "Cash Converters Telegram Sender" (`no_agent`, `deliver=telegram`, 09:10 daily)

1. **Script phase only (Layer 3), no LLM:** `run_send.sh` runs `send_formatter.py`:
   - Reads `data/pending_matches.jsonl` (written by Job A).
   - Reads `data/sent_products.json` (ledger: `product_id -> {price, sent_at}`).
   - For each pending match: DUPLICATE (same product_id + same price) -> skip silently;
     NEW (product_id never seen) or PRICE_CHANGE (product_id seen, price differs) ->
     emit.
   - For each emitted match, prints a block to stdout, blocks separated by a line
     containing exactly `---`:
     ```
     {title}
     {url}
     {price} | {store}
     Confidence: {score}/100
     ```
     (PRICE_CHANGE blocks are prefixed with a `🔔 PRICE UPDATE` line and show
     `Previous: {old_price} -> NEW: {price}` instead of a bare price line.)
   - Updates `sent_products.json` with every emitted product's new price/timestamp.
   - Clears `pending_matches.jsonl` (so nothing resends next run).
   - If nothing to send, prints nothing — `no_agent` jobs send nothing at all on empty
     stdout (confirmed safe watchdog behavior, no spurious "nothing to report" message).
2. Delivery: the scheduler hands this job's stdout straight to the live Telegram
   adapter, which splits on `---` and sends one message per block.

## Setup

### 1. Install dependencies

```bash
pip install playwright
playwright install chromium
```

### 2. Configure search criteria

Edit `data/search_criteria.json`:

```json
[
  {"search_term": "ingco", "context": "power and hand tool brand (yellow and brown)"},
  {"search_term": "wera", "context": "screw driver, and ratchet hand tools (green and black)"},
  {"search_term": "wiha", "context": "general hand tools, ratchets, spanners (red and black)"},
  {"search_term": "gadore", "context": "general hand tools, ratchets, spanners (blue and black)"}
]
```

**Context is critical** — the agent uses it to judge whether a scraped product is a real
match, not just a keyword hit.

### 3. Telegram

No bot token or chat ID needs to live anywhere in this project's files. Hermes's own
Telegram integration (configured once, globally, in Hermes Settings → Integrations)
is what Job B's stdout gets routed through. Nothing to configure here.

### 4. Create/verify the two cron jobs

```bash
hermes cron list
```

You should see:
- `Cash Converters Daily Hunt` — agent job, `script: cash_converters/run_scrape.sh`,
  schedule `every day at 09:00`, `deliver: local`.
- `Cash Converters Telegram Sender` — `no_agent` job, `script:
  cash_converters/run_send.sh`, schedule `every day at 09:10`, `deliver: telegram`.

If either is missing or misconfigured, see `hermes cron create`/`hermes cron update` —
or ask Hermes to rebuild them from this README.

## Running Manually

Test Layer 1 (scraping) alone:

```bash
cd ~/.hermes/scripts/cash_converters
python3 orchestrator.py
```

Trigger the full pipeline manually (useful for testing — fires on the next scheduler
tick, does not wait for 09:00/09:10):

```bash
hermes cron run <job-id-for-Daily-Hunt>
# wait for it to finish, confirm data/pending_matches.jsonl has content, then:
hermes cron run <job-id-for-Telegram-Sender>
```

Test Layer 3 (dedup + format) alone, without waiting on Job A:

```bash
cd ~/.hermes/scripts/cash_converters
# data/pending_matches.jsonl must already have content (hand-craft a test line if needed)
python3 send_formatter.py
```

stdout is exactly what would be sent to the Telegram adapter — inspect it for correct
`---` block formatting before trusting a live run.

## Files

### Core (required for operation)

| File | Layer | Purpose |
|------|-------|---------|
| `run_scrape.sh` | — | Job A entry point: env setup + runs orchestrator.py |
| `orchestrator.py` | 1 | Scrape per search term, output raw NDJSON, archive results |
| `scraper.py` | 1 | Playwright browser automation used by orchestrator.py |
| `config.py` | — | Shared configuration: paths, selectors, timeouts |
| `run_send.sh` | — | Job B entry point: env setup + runs send_formatter.py |
| `send_formatter.py` | 3 | Dedup against ledger, format `---` blocks, print to stdout |
| `requirements.txt` | — | Python dependencies |

Layer 2 has no dedicated file — it's entirely the cron job prompt on "Cash Converters
Daily Hunt" (`hermes cron list` / your cron management UI to view/edit it).

### User configuration

| File | Purpose |
|------|---------|
| `data/search_criteria.json` | **Your watchlist** — edit to add/remove search terms |

### Data (state & archive)

| File/Directory | Purpose |
|------|---------|
| `data/pending_matches.jsonl` | Layer 2 -> Layer 3 handoff. Ephemeral — Job B clears it every run. If you see stale entries, Job B didn't run or failed; check `hermes cron history`. |
| `data/sent_products.json` | Layer 3's dedup ledger: `product_id -> {price, sent_at}`. Delete entries (or the whole file) to force a re-send. |
| `data/results/` | Raw JSON archive from every Job A scrape (for debugging/history) |

## Customization

### Change search terms

Edit `data/search_criteria.json`. Takes effect on the next Job A run.

### Change schedule

```bash
hermes cron update <job-id-A> --schedule="every day at 10:00"
hermes cron update <job-id-B> --schedule="every day at 10:10"   # keep B ~10 min after A
```

Job B must run after Job A finishes (scraping + agent scoring takes a couple of minutes);
keep at least a 5-10 minute gap.

### Change match threshold

Edit Job A's cron prompt (the `>= 60` score cutoff) via `hermes cron update <job-id-A>
--prompt="..."`.

### Force a re-send / reset dedup

Delete (or hand-edit) `data/sent_products.json`. Everything in the next Job A run will
be treated as NEW again.

### Pause/resume

```bash
hermes cron pause <job-id>
hermes cron resume <job-id>
```

Pausing Job A stops new matches from being queued; pausing Job B stops delivery (matches
will pile up in `pending_matches.jsonl` until resumed).

## Troubleshooting

### No products scraped (Job A)

- Test manually: `python3 orchestrator.py 2>&1 | head -20`
- Check the search term actually returns results on the live site.
- Verify selectors in `config.py` haven't broken (site structure may have changed):
  `SEARCH_INPUT_SELECTOR`, `PRODUCT_ARTICLE_SELECTOR`.

### Job A runs but `pending_matches.jsonl` stays empty

- Check `hermes cron history <job-id-A>` for the agent's actual reasoning/output.
- Score threshold may be too strict for your context — broaden the context text or lower
  the `>=60` cutoff.
- Confirm the agent didn't hit a blocked-tool error (shouldn't happen — the prompt tells
  it not to use `execute_code`/`terminal`/`send_message` — but check the transcript if a
  run looks empty unexpectedly).

### Job B runs but no Telegram messages arrive

- Check `hermes cron history <job-id-B>` — if stdout was empty, there was nothing new
  to send (everything was a DUPLICATE) — this is normal, not a bug.
- Check `pending_matches.jsonl` had content before Job B ran (i.e. Job A actually
  produced matches and finished before Job B's scheduled time).
- Verify Telegram is still connected (Hermes Settings -> Integrations) — a disconnected
  adapter means delivery fails further upstream of this project's code entirely.
- Confirm `hermes config get cron.wrap_response` is `false` — if it's back to `true`
  (e.g. after a config reset), the header/footer wrapper corrupts the `---` boundaries
  and everything arrives as one combined message again.
- Confirm BOTH send paths still have their splitter: `_split_products_with_images` in
  `plugins/platforms/telegram/adapter.py` (live-adapter path) AND
  `_split_telegram_product_sections` in `tools/send_message_senders.py` (standalone
  path) — see "Two delivery send paths" above. A Hermes update could overwrite either
  file and silently drop one.
- If you just edited either of the files above and a manual test still shows the old
  behavior, see "Gotcha: a long-lived `hermes serve` process" above — you may be
  testing against stale in-memory code.

### Products scraped but never matched by the agent

- Context too strict — broaden it (e.g. "specific MacBook Pro 16GB model" ->
  "functional laptop suitable for work").
- Review the agent's actual scoring reasoning in `hermes cron history <job-id-A>`.

## Performance

- Scraping (Job A, Layer 1): ~2-3s per search term, headless Chromium.
- Agent scoring (Job A, Layer 2): a few seconds per product, scales with product count.
- Dedup + formatting (Job B, Layer 3): near-instant, pure Python, no network calls.
- Typical full run: 4 search terms, ~20-40 scraped products, a handful of real matches —
  well under the cron inactivity timeout.

## Architecture Lessons

- **Three clean layers, two jobs.** The agent (Layer 2) is the only piece that needs LLM
  reasoning; everything else is deterministic and testable in isolation.
- **Dedup lives at the delivery edge (Layer 3), not the scrape edge (Layer 1).** Keeps
  Layer 1 simple/stateless and keeps the one source of truth for "have we sent this
  before" next to the one process that actually sends.
- **The agent can never send messages directly in cron.** `send_message` is
  unconditionally unavailable to cron-spawned agents; design around it, don't fight it.
- **Secrets can never reach cron script subprocesses.** `TELEGRAM_BOT_TOKEN` is
  permanently stripped; don't design a script that assumes it can call the Telegram API
  itself from a cron job.
- **Delivery is content-agnostic between agent and `no_agent` jobs.** Both end up at the
  same `adapter.send()` call, so a `no_agent` script's stdout gets exactly the same
  `---`-splitting treatment an agent's final response would. This is the load-bearing
  fact that makes the whole Job B design possible.

## Status

✅ **Rebuilt and verified end-to-end 2026-10-06** — replaced the single-job,
`---`-in-final-response design (which silently produced one giant unreadable Telegram
message whenever the `no_agent` shortcut was on, and wasted agent turns on blocked tool
calls when it wasn't) with this two-job, three-layer pipeline. Dedup moved from Layer 1
to Layer 3 per design decision.

Fixed along the way (see "Two delivery send paths" and the `serve`-process gotcha above):
`cron.wrap_response` disabled globally, `_send_telegram` standalone sender patched to
split on `---` same as the live adapter. Confirmed live with real scraped Cash Converters
data: 21 matches scored by the agent, 6 genuinely new/changed after dedup, all 6 arrived
as separate Telegram messages.

Search criteria active: `ingco`, `wera`, `wiha`, `gadore` (hand/power tool brands).

---
name: Scheduled Agent Automation
description: Build cron jobs that scrape and deliver via Agent.
trigger: 'Use when building a cron job where a Python/shell script scrapes or gathers data, and a Hermes Agent (Claude) processes it and delivers to external services (Telegram, Slack, email, etc.)'
keywords: cron, scheduled job, agent processing, data pipeline, Telegram delivery
---

# Scheduled Agent Automation

Build repeating cron jobs that scrape/gather data via script and delegate analysis + delivery to Hermes Agent.

## Architecture (Canonical Pattern)

```
Cron Job (scheduled time)
    ↓ run.sh (environment wrapper)
    ↓
Python/Shell Script (gather data only)
    ↓ [structured data to stdout: JSON, CSV, or plain text]
    ↓
Hermes Agent (Claude AI receives via cron prompt)
    ↓ [analysis, filtering, formatting]
    ↓
External Service (Telegram, Slack, email, etc.)
```

## Procedure

### 1. Write the Data-Gathering Script

**Scope:** Script outputs ONLY raw data. No formatting, no delivery logic, no external API calls (except target site).

```python
#!/usr/bin/env python3
"""Example: Scrape products and output JSON."""
import json
from playwright.sync_api import sync_playwright

# Load configuration
config = load_config()  # search terms, criteria, etc.

# Gather data
results = []
for term in config['search_terms']:
    products = scrape_site(term)
    results.append({
        'search_term': term,
        'context': config['context'],
        'products': products  # Raw product data only
    })

# Output to stdout (Hermes Agent will read this)
print(json.dumps({'timestamp': utcnow(), 'searches': results}))
```

**Key rules:**
- Output structured data only (JSON preferred, CSV/text acceptable)
- Print to stdout (Hermes Agent receives this as cron script output)
- No Telegram sends, no message formatting, no attachments
- Errors to stderr (cron logs separately, Agent sees on retry)
- Keep dependencies minimal (Playwright for scraping; no async, no image libraries unless data needs them)
- Make script testable locally: `python3 script.py` should output valid JSON

### 2. Create run.sh Wrapper

Cron environments often lack Python path or browser dependencies. Wrap in shell:

```bash
#!/bin/bash
# Ensure dependencies installed
pip install -q playwright 2>/dev/null || true
playwright install chromium 2>/dev/null || true

# Export PYTHONPATH if custom modules
export PYTHONPATH="/path/to/modules:$PYTHONPATH"

# Run script
cd "$(dirname "$0")"
python3 orchestrator.py
```

**Why separate wrapper:** Cron has minimal environment; script may not find Python libs or browser binaries. Wrapper ensures they exist before script runs.

### 3. Write the Agent Prompt

Cron jobs set a `--prompt` that tells Agent what to do with the data. See `references/agent-prompt-template.md` for reusable prompt boilerplate and examples.

**Prompt structure:**

```
Input format: [describe structure of script output]
For EACH [item in data]:
  1. ANALYZE [against what criteria?]
  2. FILTER [keep only items scoring ≥X%]
  3. SEND [to Telegram/Slack/email with what format?]

Output: Send messages to [service]. Print nothing to stdout. Errors to stderr.
```

**Example (product hunting):**

```
Input: JSON with searched products {title, price, store, url}.

For EACH product:
  1. Score 0-100 vs context (price range, category, condition).
  2. Keep only ≥60% confidence.
  3. Send ONE Telegram message: title (bold), [link](url), price, store, reasoning.

Output: Messages to Telegram. Nothing to stdout. Errors to stderr.
```

**Key rules:**
- Describe input format (structure Agent will receive)
- Specify decision criteria (what "match" means)
- Specify output format per service (Telegram markdown syntax, Slack blocks, email text)
- Tell Agent to produce one message per item or batch, per your preference
- Say "nothing to stdout, errors to stderr" (keeps cron logs clean)

### 4. Set Up Cron Job

Create or edit:

```bash
hermes cron create --name="Job Name" \
  --script="path/to/run.sh" \
  --schedule="every day at 09:00" \
  --prompt="[your prompt from step 3]"
```

Or edit existing:

```bash
hermes cron edit <job-id> --prompt="[new prompt]"
```

Verify:

```bash
hermes cron list
hermes cron history <job-id>  # See past runs
```

### 5. Test End-to-End

1. Run script locally: `python3 orchestrator.py` → verify JSON output
2. Run cron manually: `hermes cron run <job-id>` → check result in Telegram/Slack/email
3. Check cron logs: `hermes cron history <job-id>` → look for errors

## Lessons

### Lesson: Keep Script and Agent Concerns Separate
Script gathers data only. Agent decides what data matters and formats for delivery. Do not put filtering, scoring, or formatting in the script — that is Agent's job. Reason: Agent can adjust behavior (thresholds, format) by just editing the cron prompt; script only changes if data source changes.

### Lesson: Simplify Over Time; Remove Over-Engineering
Common mistake: script downloads images, attaches files, formats HTML, pre-filters data. All of this adds dependencies and maintenance burden. If Agent can work with plain text + link, remove image download. If Agent can filter, remove filtering code from script. Reason: Agent is better at context-aware decisions than hardcoded rules.

### Lesson: Output Structured Data, Not Text
Script should output JSON (or CSV, or structured text), not a formatted "message" or human-readable report. Reason: Agent can parse and analyze structured data flexibly. A pretty-printed message is harder to machine-parse and harder to reformat for a different service later.

### Lesson: Dependencies in run.sh, Not in Script
Script assumes Playwright is installed. Cron may not have it. Put install logic in run.sh (silent, non-failing: `2>/dev/null || true`). Reason: Script is portable, wrapper is environment-specific.

### Lesson: Test Script Locally Before Cron
Run `python3 orchestrator.py` locally and verify JSON output before adding to cron. Reason: Debugging a failed cron is harder than debugging a failed local run; better to catch errors early.

### Lesson: Print Data to stdout, Errors to stderr
Script prints JSON to stdout (Agent receives this). Errors go to stderr (cron logs separately). Do not print status or debug info to stdout. Reason: Agent parses stdout as data; mixed output breaks parsing.

### Lesson: One-Time Delivery per Product vs. Batch
Decide: send one message per matched product (sequential, more personal) or batch all into one message (faster, summary). State this clearly in Agent prompt. Reason: Affects how Agent formats output and affects delivery speed.

### Lesson: Cron Agents Cannot Self-Deliver — Split Scoring and Sending Into 2 Jobs
A single cron job's agent CANNOT call `send_message` (the `messaging` toolset is unconditionally stripped from cron-spawned sessions, loop-prevention, no override) and CANNOT fall back to `execute_code`/`terminal` to send manually (these are sandbox-BLOCKED in cron — there is no user present to approve the subprocess call). If your pipeline needs an LLM to score/match AND then deliver per-item messages, you cannot do both inside one job's agent turn. Split into 2 cron jobs on a staggered schedule (e.g. 09:00 and 09:10):
- **Job A** (`no_agent:false`, `deliver:local`): script scrapes raw data, agent scores/filters it, agent writes results to a shared file (`write_file` survives the cron toolset strip) instead of trying to send anything.
- **Job B** (`no_agent:true`, `deliver:<platform>`): a pure script reads Job A's file, formats it (including dedup bookkeeping — this is also the natural place for a dedup ledger), and exits. The script never touches the platform API directly or needs its token — it emits `---`-delimited stdout and lets the cron delivery pipeline (which does hold the real credentials in the long-lived gateway process) do the actual per-block sends.
This also keeps API tokens out of script subprocesses entirely, which matters because of the next lesson.

### Lesson: Platform Secrets Are Stripped From Every Script Subprocess, No Override
`TELEGRAM_BOT_TOKEN`-class provider secrets are deliberately stripped from ALL spawned subprocess environments (terminal, execute_code, cron scripts) by a hard security policy with no passthrough override. Do not design a script that expects to read a bot token from its env and call the platform API directly — it will always fail with "not set", and there is no config flag to fix it. The only sanctioned path for a script to deliver a message is to print `---`-delimited stdout and let the cron delivery pipeline relay it (see the `---` separator lesson above) — never have the script call the platform API itself.

### Lesson: Verify Which Delivery Path Actually Ran Before Trusting a Patch
There are multiple distinct code paths that can deliver cron output to a platform (e.g. a "live adapter" path reused from the chat-session delivery pipeline, and a separate "standalone sender" path used when no interactive session is live) — a splitting/formatting fix applied to only one of them can look right in the code but silently not fire, because the job actually ran through the other path. If a cron fix doesn't take effect, check the delivery log line format first (presence/absence of phrases like "via live adapter") to identify which path handled the run before debugging further — don't assume the path you patched is the one that executed.

### Lesson: `cron.wrap_response: true` (the default) Corrupts `---` Delimiters
By default Hermes wraps every delivered cron response with a header ("Cronjob Response: ...\n-------------\n\n") and a footer. That wrapper text itself contains `---`-like sequences and extra boundaries, which can break a script's own `\n---\n` item-separators and merge/garble the per-item split. If you rely on `---` delimiters for per-item delivery, set `cron.wrap_response: false` globally (`hermes config set cron.wrap_response false`) — it's cosmetic for every job, not worth leaving on while debugging a delimiter-splitting bug.

### Lesson: Restarting the Gateway Does Not Guarantee the Backend Process Restarted
If you edit core Hermes Python files (adapters, senders, delivery logic) and `hermes gateway restart` doesn't seem to pick up the change no matter how certain you are the file is correct on disk, check `ps aux | grep "hermes serve"` for the actual backend process's start time before concluding the code itself is wrong. A `serve` process that predates your edits can keep running in-memory old code through a "restart" that only reloads config/adapters, not the Python process itself; kill and respawn it explicitly and recheck its PID/start time to confirm the new code is actually live.

### Lesson: Cron Delivery Routes by Platform, Not By Bot Identity
Cron jobs target services by platform name (`telegram`, `slack`, `email`, etc.), not by hardcoded bot name or agent identity. When reviewing a job before rebranding an agent (e.g., renaming from "default" to "echo"), the Telegram delivery will not break — the gateway uses active session routing, not identity resolution. Verify this by checking the job's `deliver` field in `~/.hermes/cron/jobs.json` (e.g., `"deliver": "telegram"`, not `"deliver": "bot-chat:echo"`) and confirming `"origin": null` (default routing). If origin is null, the job routes to ANY active session of that platform and continues working regardless of agent name changes. Reason: Hermes platform routing is session-based; bot identity is orthogonal to delivery. No reconfiguration needed after renaming the agent.

### Lesson: Force Separate Deliveries Using Output Delimiters
**CRITICAL:** Hermes cron `--deliver=telegram` (and other services) **batches the entire agent response into ONE delivery by default**. If you need N individual messages (one per product, one per alert, etc.), use `---` block separators in Agent output.

**How it works:** Agent formats each item with `---` delimiters:
```
---
Item 1 Title
Item 1 details
---

---
Item 2 Title
Item 2 details
---
```
Hermes cron gateway sees the `---` boundaries and splits them into separate deliveries — one Telegram message per block.

**When this hits:** You test cron, it succeeds, but users get one giant message instead of N items. You set `--prompt="send one message per product"` but it has no effect. This is the cron gateway's default batching behavior, not the Agent's fault.

**Solution:** Tell Agent to output `---` block delimiters before and after each item. Phrase the prompt:
```
For each matched product, output:
---
{title}
{url}
{price} | {store}
Confidence: {score}/100
---

Then blank line before next product. The --- separator tells Hermes to send as separate message.
```

Hermes gateway automatically splits on `---` and delivers each block separately. This is the canonical pattern for "one message per item" via cron.

**Alternative (Pattern B):** If the script itself needs to send individual messages (not Agent), script calls `hermes send --to telegram` directly per item instead. Trade-off: you do filtering in Python (not Agent), but gain fine-grained control. See the `web-scraping-with-ai-filtering` skill's `references/direct-script-delivery.md` for details.

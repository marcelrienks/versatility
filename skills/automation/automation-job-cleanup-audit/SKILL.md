---
name: automation-job-cleanup-audit
description: "Audit jobs, remove bloat files safely, verify operation."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: automation
    tags: [cron, cleanup, audit, disk-usage, job-hardening]
    related_skills: [cash-converters-automation]
---

# Automation Job Cleanup & Audit

Use when a cron job or scheduled automation has accumulated significant files (Git history, debug logs, old runners, versioned documentation) and you need to identify what is operational vs. safe to delete.

## Procedure

### Phase 1: Map the Job

1. **Understand the job architecture**
   - What scripts run? (entry point, drivers, workers)
   - What do they produce? (output files, archives, caches)
   - Who configures it? (config files, user input)
   - How does it integrate? (Hermes Agent, cron, external services)
   
2. **Find the job directory**
   ```bash
   find /home/opc/.hermes/scripts -maxdepth 2 -type d -name "*jobname*"
   ```
   (or check `~/.hermes/cron/` for registered jobs)

3. **List all files by category**
   ```bash
   find /path/to/job -type f | sort
   du -sh /path/to/job/*  # size breakdown
   ```

### Phase 2: Categorize Files

Build a table of what exists. Use these categories:

| Category | Examples | Delete? | Why |
|----------|----------|---------|-----|
| **Core runtime** | `run.sh`, `orchestrator.py`, `scraper.py`, `config.py`, main executables | ✅ KEEP | Job will not run without them |
| **User configuration** | `search_criteria.json`, settings files, API keys stored locally | ✅ KEEP | User data, not ours to delete |
| **Output archives** | `data/results/` timestamped JSON, `data/cache/`, product images | ✅ KEEP | Historical records, user may audit |
| **Documentation** | `README.md`, `SETUP.md` | ✅ KEEP ONE | Consolidate duplicates; keep best/latest |
| **Git history** | `.git/` directory | ❌ DELETE | Not needed after automation is stable; can grow 1-5 MB |
| **Old logs** | `cron_<id>_timestamp`, `run_*.log` | ❌ DELETE | Stale; Hermes retains cron history separately |
| **Alt/redundant runners** | `run_telegram.sh`, `run_no_agent.sh`, `hunt.sh` | ❌ DELETE | Replaced by current `run.sh` |
| **Old/integrated code** | `hunt_and_send.py`, `telegram_sender.py` (obsolete modules) | ❌ DELETE | Superseded by Hermes Agent |
| **Development/debug** | `test_analyzer.py`, `data/debug_screenshots/`, `.gitignore`, `git-quick-ref.sh` | ❌ DELETE | Debug artifacts, setup helpers |
| **Bytecode** | `__pycache__/`, `*.pyc` | ❌ DELETE | Regenerates on import; bloat |

### Phase 3: Verify Core Files Compile

Before deleting anything, ensure all runtime Python files still work:

```bash
cd /path/to/job
python3 -m py_compile orchestrator.py scraper.py config.py main_script.py
echo $?  # 0 = success, non-zero = error
```

If any fail, **STOP** — track down the error before proceeding.

### Phase 4: Audit Configuration & Data

1. **Load and validate user config**
   ```bash
   python3 -c "import json; f = json.load(open('data/search_criteria.json')); print(f'{len(f)} items')"
   ```

2. **Check data directories exist and have content**
   ```bash
   ls -lh data/results/ data/image_cache/ data/cache/
   find data/results -type f | wc -l
   ```

3. **Verify entry point is executable**
   ```bash
   ls -l run.sh  # should show 'x' in permissions
   ```

### Phase 5: Execute Cleanup

Delete in this order (most-safe first):

1. **Bytecode & caches** (always safe)
   ```bash
   rm -rf __pycache__ *.pyc *.pyo
   ```

2. **Debug artifacts** (safe; not config or code)
   ```bash
   rm -rf data/debug_screenshots data/cache
   rm -f git-quick-ref.sh .gitignore
   ```

3. **Old logs** (safe; Hermes retains history)
   ```bash
   rm -f cron_*_timestamp  # e.g., cron_b21a20eb7f23_20260923_054456
   rm -f run_*.log
   ```

4. **Redundant code** (safe if you verified entry point works)
   ```bash
   rm -f run_telegram.sh run_no_agent.sh hunt.sh
   rm -f hunt_and_send.py orchestrator_telegram.py telegram_sender.py
   rm -f test_analyzer.py
   ```

5. **Documentation versions** (consolidate first — see Phase 6)
   ```bash
   rm -f SETUP_COMPLETE.md AGENT_PROMPT.md CRON_PROMPT.txt *.txt
   rm -f README_FINAL.md  # keep only one README.md
   ```

6. **Git history** (last; irreversible but safe once code verified)
   ```bash
   rm -rf .git/
   ```

### Phase 6: Consolidate Documentation

Before deleting old .md files:

1. **Read all documentation files**
   - Identify what is outdated vs. still-relevant
   - Extract unique content from each

2. **Update the primary README.md with**
   - Complete architecture diagram
   - All operational procedures
   - Troubleshooting section
   - Customization recipes
   - Links to any data structure references

3. **Delete all other .md versions** (SETUP_COMPLETE, AGENT_PROMPT, etc.)

## Pitfalls

**Pitfall: Deleting configuration before consolidating it.** Always read `search_criteria.json`, API keys, or user settings before removing anything — if it's lost and undocumented, the user must recreate it. Snapshot it in the main README or a `references/` support file if it documents decision logic.

**Pitfall: Deleting `.git/` before verifying code runs.** Run `python3 -m py_compile` on all runtime files first; if anything fails, Git history is your emergency rollback. Only delete `.git/` once you have confirmed all scripts compile and the job passed a manual test run.

**Pitfall: Keeping test or debug files that import stale modules.** If you delete `old_module.py` but `test_analyzer.py` imports it, the test will fail silently on next run. Delete test files along with their imports; never leave orphan imports.

**Pitfall: Not checking whether the entry script has changed.** If `run.sh` used to call `run_telegram.sh` and you deleted it, the job will break. Always inspect `run.sh` and confirm no other scripts depend on files you are about to delete.

**Pitfall: Confusing `data/cache/` with `data/image_cache/`.** The image cache contains live product images needed for delivery (keep it); an empty `cache/` dir is bloat. Check directory size before assuming it is safe to delete.

## Verification Checklist

After cleanup, verify:

- [ ] All Python files compile: `python3 -m py_compile *.py`
- [ ] User config is valid: `python3 -c "import json; json.load(open('config.json'))"`
- [ ] Data directories present: `ls -lhd data/results data/image_cache`
- [ ] Entry script is executable: `ls -l run.sh | grep x`
- [ ] No .pyc or __pycache__ remain: `find . -name '*.pyc' -o -name '__pycache__'`
- [ ] No orphan imports in remaining code: grep for imports of deleted modules in remaining .py files
- [ ] Manual test (if possible): `/path/to/job/run.sh` or `python3 orchestrator.py` runs without errors

## Space Recovery

Typical cleanup recovers:
- `.git/` directory: 1–5 MB (full Git history)
- Old cron logs: 1–10 MB (per log)
- Debug screenshots: 50–200 KB
- __pycache__: 50–100 KB
- Old documentation (15 files): 50–150 KB

**Total typical recovery: 2–15 MB per job** depending on how many iterations and debug cycles accumulated.

## Persistent Ledger Deduplication

Many automation jobs track state (what has been sent, what has changed) using a persistent ledger file. See `references/persistent-ledger-dedup.md` for the three-category model (NEW, UPDATED, DUPLICATE) and implementation patterns.

## Cleanup & Ledger Safety

**Pitfall: Cleanup removes old entries but ledger is single source of truth for dedup.** If cleanup removes an entry (>90 days old) and the item reappears later, it will be treated as NEW again, triggering a re-send. This is by design (refreshes stale tracking), but users may be surprised. Document this behavior in job README so users understand automatic cleanup lifecycle.

**Pitfall: Cleanup modifies ledger before scraper runs.** If cleanup removes entries and immediately after the scraper finds the same items, those items are classified as NEW instead of DUPLICATE. The sequence (cleanup → scrape → deduplicate) matters. Always run cleanup at job START, before any scraping or comparison logic.

## Refs

- cash-converters-automation: Real example of this workflow applied to a production Playwright + Hermes Agent job
- persistent-ledger-dedup.md: Three-category deduplication model and ledger structure patterns

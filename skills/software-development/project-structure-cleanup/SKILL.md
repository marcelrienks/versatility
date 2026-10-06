---
name: project-structure-cleanup
description: "Flatten and reorganize automation job directories safely."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: software-development
    tags: [automation, cron, directory-structure, refactoring, relative-paths]
    related_skills: [cash-converters-automation, systematic-debugging]
---

# Project Structure Cleanup

Restructure and clean up automation projects (cron jobs, scripts, data) while keeping all cross-references functional. Use when flattening nested directories, moving files, or removing obsolete structure without breaking scheduled execution.

## Use When

You have an automation project with:
- Nested subdirectories (e.g., `scripts/project/project/...`)
- Multiple references to the old structure (cron config, shell scripts, Python code)
- Running scheduled jobs that must not break during restructuring
- Documentation that needs updating

## Procedure

### 1. Map Current Structure

Before moving anything, document:
- Current directory tree
- All files and their purposes
- All cross-references (grep the cron job config, scripts, docs, code)

```bash
find ~/.hermes/scripts/PROJECT -type f -o -type d | sort
grep -r "PROJECT" ~/.hermes/cron/jobs.json
grep -r "PROJECT" ~/.hermes/scripts/PROJECT/*.py
```

**WHY:** Know what you're changing before you change it. Missing a reference breaks the job silently at next scheduled run.

### 2. Plan the New Structure

Decide:
- Which subdirectories to keep (data, configs)
- Which to flatten (code files)
- Whether to use relative or absolute paths in the new setup

**PITFALL:** Using absolute paths in shell scripts or Python. A future move breaks everything silently. Use relative paths instead:
- Shell: `cd "$(dirname "$0")"` (cd to script's directory)
- Python: `Path(__file__).parent` (parent of the defining module)

### 3. Update the Cron Job First

Before moving files, update `~/.hermes/cron/jobs.json` with the new script path. Use relative paths (relative to `~/.hermes/scripts/`):

```bash
jq '.jobs[0].script = "new/path/to/run.sh"' jobs.json.bak > jobs.json
```

**WHY:** The cron job holds the canonical reference. If you change it AFTER moving files, the job fails and you won't know until the next scheduled run (hours later). Change config first, then move.

### 4. Move Files

Move all files to their new locations:

```bash
mkdir -p ~/.hermes/scripts/PROJECT
mv old/path/* ~/.hermes/scripts/PROJECT/
rmdir old/path  # verify it's empty first
```

### 5. Update Entry Point Script

The script that cron calls (e.g., `run.sh`) must work from its new location. Use relative paths:

```bash
#!/bin/bash
cd "$(dirname "$0")"  # cd to this script's directory
/usr/bin/python3 orchestrator.py
```

NOT: `cd /home/opc/.hermes/scripts/PROJECT` (absolute path breaks on any move).

**WHY:** `$(dirname "$0")` works anywhere. Absolute paths don't survive restructuring.

### 6. Update Python Code

Check for hardcoded paths in Python files:

```bash
grep -r "/home/opc" *.py
```

Replace with relative paths:

```python
from pathlib import Path
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
```

NOT: `DATA_DIR = Path("/home/opc/.hermes/scripts/PROJECT/data")`

### 7. Update Documentation

Update README, comments, and examples to reflect the new structure and location. Include multiple ways to invoke the script:

```bash
# Method 1: from within the project directory
cd ~/.hermes/scripts/PROJECT
python3 orchestrator.py

# Method 2: from scripts directory
cd ~/.hermes/scripts
python3 PROJECT/orchestrator.py
```

### 8. Verify All References

Grep for the old structure everywhere:

```bash
grep -r "old/path" ~/.hermes/scripts/
grep -r "old/path" ~/.hermes/cron/
grep -r "old/path" ~/.hermes/*.md
```

If anything matches, update it or confirm it's historical (old session dumps, archived results).

**WHY:** A forgotten reference in code or config causes silent failures. The cron job runs, the script runs, but the wrong working directory breaks everything.

### 9. Test the Job

Manually run the entry point script to verify it works from the new location:

```bash
bash ~/.hermes/scripts/PROJECT/run.sh
```

If it fails, the relative path setup is wrong—fix it before the scheduled job runs and fails silently.

## Lessons

### Relative paths are non-negotiable for relocatable projects
Absolute paths in cron scripts, shell wrappers, or Python code create silent failures when the project moves. Use `$(dirname "$0")` in bash, `Path(__file__).parent` in Python. If you see an absolute path, it is a bug waiting to happen—fix it immediately.

### Update the cron config BEFORE moving files
If you change the job config after moving files, the interval before the next scheduled run is silent failure time. The user won't know anything broke until the job is due. Config changes always come first.

### Search for old paths after restructuring
A single forgotten reference in a Python import, a shell script, or a commented example breaks the job silently. After moving, grep the entire project tree (and cron config) for any trace of the old path. Do not rely on memory—grep.

### Data files (results, archives, cache) can stay in subdirectories
Code files should be at the project root or organized by clear purpose. Data files (`results/`, `image_cache/`, `config.json`) can live in a `data/` subdirectory. This separation is cleaner than flattening everything.

### User will correct you on structure — listen and adapt
When a user says "I want project/..., not project/project/...", honor that immediately. Do not defend the original nesting. Update the plan and re-execute. Structure is a preference, not a default.

## References

- **`references/relative-path-patterns.md`** — Code examples and anti-patterns for bash `$(dirname "$0")` and Python `Path(__file__).parent`
- **`references/cron-path-verification.md`** — Why to update cron config first, how to verify job paths, checking `jobs.json` for correct relative paths

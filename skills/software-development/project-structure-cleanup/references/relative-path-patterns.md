# Relative Path Patterns for Relocatable Projects

## Problem

Absolute paths in automation scripts create fragility:
- Cron job calls `run.sh`
- `run.sh` does `cd /home/opc/.hermes/scripts/PROJECT`
- Project later moves to `~/.hermes/other_location/PROJECT`
- Cron job still runs, but from wrong directory
- Silently fails until discovered hours/days later

## Solution: Relative Paths

### Shell (bash, sh)

**Use `$(dirname "$0")` to cd to the script's own directory:**

```bash
#!/bin/bash
# run.sh

cd "$(dirname "$0")" || exit 1

# Now we're in the directory where run.sh lives
python3 orchestrator.py
```

**Why:** `$0` is the path to the script itself (how bash invoked it). `dirname` extracts the directory part. Works everywhere:
- Called as `bash ./run.sh` → cd to `.`
- Called as `bash /full/path/run.sh` → cd to `/full/path`
- Called from cron as `run.sh` → cd to wherever cron is configured to run it from

### Python

**Use `Path(__file__).parent` to find the script's directory:**

```python
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
RESULTS_DIR = DATA_DIR / "results"

# Load data file relative to script
with open(SCRIPT_DIR / "config.json") as f:
    config = json.load(f)
```

**Why:** `__file__` is the path to the currently executing module. `Path(__file__).parent` is its directory. All subsequent paths are relative to that anchor, so moving the entire project tree works without any code changes.

### Python Config Class Pattern

```python
from pathlib import Path

class Config:
    """Project paths, computed relative to this file."""
    
    SCRIPT_DIR = Path(__file__).parent
    DATA_DIR = SCRIPT_DIR / "data"
    RESULTS_DIR = DATA_DIR / "results"
    IMAGE_CACHE_DIR = DATA_DIR / "image_cache"
    SEARCH_CRITERIA_FILE = DATA_DIR / "search_criteria.json"

# Anywhere in the codebase:
with open(Config.SEARCH_CRITERIA_FILE) as f:
    criteria = json.load(f)
```

## Anti-Patterns (Don't Do These)

### Bad: Hardcoded absolute path

```bash
cd /home/opc/.hermes/scripts/PROJECT  # BREAKS if project moves
```

```python
DATA_DIR = Path("/home/opc/.hermes/scripts/PROJECT/data")  # BREAKS if project moves
```

### Bad: Path built from environment variable (unless you control the variable)

```bash
cd "$HOME/.hermes/scripts/PROJECT"  # BREAKS if project moves or user home changes
```

### Bad: Assuming current working directory

```python
import os
data_file = os.path.join(os.getcwd(), "data", "results.json")  # BREAKS if cron runs from different cwd
```
The cron job might run from `/`, `/tmp`, or anywhere else depending on configuration.

## Verification Checklist

After restructuring, grep for absolute paths:

```bash
grep -r "/home/opc" *.py *.sh
grep -r "/root" *.py *.sh
grep -r "\$HOME" *.py *.sh  # Not always wrong, but suspicious in cron context
```

If you find any, replace them with relative paths.

## Real Example: Cash Converters Job

**Before (fragile):**
```bash
#!/bin/bash
cd /home/opc/.hermes/scripts/cash_converters
python3 orchestrator.py
```

**After (relocatable):**
```bash
#!/bin/bash
cd "$(dirname "$0")"
python3 orchestrator.py
```

**Result:** Move the entire `cash_converters/` directory anywhere. The script still works.

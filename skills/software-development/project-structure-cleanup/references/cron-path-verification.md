# Cron Job Path Reference Verification

## The Critical Step: Config First, Then Move

When restructuring a project that has a scheduled cron job:

1. **Update `~/.hermes/cron/jobs.json` FIRST** — before moving any files
2. Then move the files
3. Then update all code references

If you move files before updating the cron config, the job will fail silently at the next scheduled run. You won't know for hours (or until manual execution).

## Checking Current Cron Config

```bash
jq '.jobs[] | {name, script}' ~/.hermes/cron/jobs.json
```

Look for the job by name and note the `script` field — this is a path relative to `~/.hermes/scripts/`.

## Updating Cron Script Path

```bash
# Backup first
cp ~/.hermes/cron/jobs.json ~/.hermes/cron/jobs.json.bak

# Update the script path (example)
jq '.jobs[0].script = "cash_converters/run.sh"' jobs.json.bak > jobs.json

# Verify the change
jq '.jobs[0].script' jobs.json
```

Or use a filter to find the job by name:

```bash
jq '.jobs[] | select(.name == "Cash Converters Daily Hunt") | .script' jobs.json
```

## Why This Order Matters

**Scenario: You move files FIRST, then update cron config**

1. Move `old/path/run.sh` → `new/path/run.sh`
2. Update cron config to point to `new/path/run.sh`
3. Time passes...
4. Scheduled job time arrives (next day, for example)
5. Cron tries to run the old path (still in memory or from old config snapshot)
6. Job fails silently
7. User doesn't know anything is wrong until they check or wait for the next manual run

**Scenario: You update cron config FIRST, then move files**

1. Update cron config to point to `new/path/run.sh`
2. Move files to the new location
3. Scheduled job time arrives
4. Cron runs with correct path
5. Job succeeds

No silent failure window.

## Relative Path Format in jobs.json

The `script` field in `jobs.json` is always relative to `~/.hermes/scripts/`.

- Good: `"script": "cash_converters/run.sh"`
- Good: `"script": "my_job/entry_point.py"`
- Bad: `"script": "/home/opc/.hermes/scripts/cash_converters/run.sh"` (absolute path)
- Bad: `"script": "./cash_converters/run.sh"` (relative to cwd, not to scripts/)

## After Moving: Verify the Job Still Works

```bash
# Manually run the script to verify it works from the new location
bash ~/.hermes/scripts/new/path/run.sh

# Or check the cron config one more time
jq '.jobs[] | select(.name == "Your Job Name") | {script, schedule, last_status}' ~/.hermes/cron/jobs.json
```

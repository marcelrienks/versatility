# Cron Job Dependency Audit: Before Rebranding an Agent

When renaming or rebranding a Hermes Agent, verify that existing cron jobs do not hardcode the agent's identity and will continue working after the rename.

## Quick Checklist

### 1. Review Job Delivery Configuration

Open `~/.hermes/cron/jobs.json` and examine each job's delivery setup:

```bash
cat ~/.hermes/cron/jobs.json | python3 -m json.tool | grep -A 3 -B 3 '"deliver"\|"origin"'
```

**What to look for:**

- ✅ **Safe:** `"deliver": "telegram"` with `"origin": null` — routes by platform name, not identity
- ✅ **Safe:** `"deliver": "slack"` with `"origin": null` — routes by platform name, not identity
- ✅ **Safe:** `"deliver": "email"` with `"origin": null" — routes by platform name, not identity
- ❌ **At risk:** `"deliver": "bot-chat:oldname"` — hardcodes old bot identity; will NOT route after rename
- ❌ **At risk:** `"origin": "some-old-bot-name"` — hardcodes old origin; may not route after rename

**Platform-Based Routing (Safe):**
Jobs with `"deliver": "telegram"` (or slack, email, etc.) and `"origin": null` route to ANY active session of that platform. After rename, the same platform is still active, so delivery continues uninterrupted.

**Identity-Based Routing (At Risk):**
Jobs with `"deliver": "bot-chat:name"` or an explicit origin route to a NAMED bot/profile. After rename, that name no longer exists (unless you rename the profile itself), and delivery fails.

### 2. Examine Script Files for Hardcoded Bot Name

Check the script that runs in each job (see the `"script"` field in the job config):

```bash
grep -r "bot\|name\|identity\|profile" ~/.hermes/cron/output/*/script.py
```

**What to look for:**

- Bot name literal (e.g., `"bot_name='default'"`)
- Hardcoded URL or API endpoint with bot name
- Config file with bot identity

**If found:** Update the script or move the bot name to a config file the script reads at runtime (not hardcoded).

### 3. Check run.sh for Environment Variables

Examine the run.sh wrapper:

```bash
cat ~/.hermes/scripts/cash_converters/run.sh  # Replace path with your job's script
grep -i "bot\|hermes_\|profile" run.sh
```

**What to look for:**

- `HERMES_HOME` or profile-scoped env vars — these are ✅ safe (resolved at runtime)
- Hardcoded bot name or profile name — ❌ at risk

**If found:** Use `hermes config` to read values at runtime instead of hardcoding.

### 4. Check Cron Job Prompt for Identity References

The cron job's `"prompt"` field in jobs.json tells the Agent what to do. Examine it:

```bash
cat ~/.hermes/cron/jobs.json | python3 -m json.tool | grep -A 50 '"prompt"' | head -60
```

**What to look for:**

- References to "bot" name or identity in instructions
- Hardcoded routing (e.g., "send to bot X")

**If found:** Edit the prompt to use dynamic routing instead. For example:

```
Before: "Send results to bot 'default' via Telegram"
After:  "Send results via Telegram (default platform routing)"
```

### 5. Check Script Output for Bot Name

If the script generates output (NDJSON, JSON, text), verify it doesn't embed the bot name:

```bash
python3 ~/.hermes/scripts/your_script.py | head | grep -i "bot\|name"
```

**If found:** Remove bot name from output. The Hermes gateway doesn't need it; it routes based on the cron job config, not the script output.

## Action Required

For each job marked **At Risk**:

### If `deliver: bot-chat:oldname`

**Option A: Update to platform-based delivery (recommended)**

```bash
hermes cron update <job-id> --deliver="telegram"  # or slack, email, etc.
```

This routes to ANY active session of that platform after rename.

**Option B: Update to bot-chat with new name**

```bash
hermes cron update <job-id> --deliver="bot-chat:echo"
```

This routes to the renamed profile (requires profile rename to match, or cross-profile bot-chat setup).

### If hardcoded bot name in script or prompt

Edit the job:

```bash
hermes cron edit <job-id>
```

Remove or generalize bot name references in the prompt. Use platform names ("Telegram", "Slack") instead of bot identities ("oldbot", "newbot").

## Example: Verified Safe Job

```json
{
  "id": "04ff6d3c1fdb",
  "name": "Cash Converters Daily Hunt",
  "deliver": "telegram",
  "origin": null,
  "script": "cash_converters/run.sh",
  "no_agent": true
}
```

**Why safe:**
- `"deliver": "telegram"` — routes to platform, not bot name
- `"origin": null` — default routing (no bot specified)
- Script (`cash_converters/run.sh`) gathers data only, no bot name hardcoded
- No bot name in cron prompt

After renaming agent to "echo", this job continues routing to Telegram automatically. No changes needed.

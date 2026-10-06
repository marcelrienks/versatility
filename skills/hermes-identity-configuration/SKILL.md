---
name: hermes-identity-configuration
description: "Rename/rebrand Hermes Agent, manage identity and profiles."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: autonomous-ai-agents
    tags: [hermes, identity, configuration, profiles, rebranding, metadata]
---

# Hermes Identity & Configuration Management

Manage agent identity, rename instances, and handle multi-profile configuration. Use when rebranding a Hermes Agent instance or updating identity-related metadata.

## Procedure: Rename/Rebrand a Hermes Agent

### 1. Identify the Target Profile

Determine which profile to rename:

```bash
hermes config get agent  # Show current agent config
echo $HERMES_HOME        # Show active profile home (default: ~/.hermes)
```

**Default profile:** `$HERMES_HOME = ~/.hermes`
**Named profile:** `$HERMES_HOME = ~/.hermes/profiles/<name>` (set explicitly)

### 2. Update Agent Identity Configuration

Set the agent name, identity, and display title using `hermes config set` (never hand-edit config.yaml):

```bash
hermes config set agent.name echo
hermes config set agent.identity echo
hermes config set display.title echo
```

**Why three keys?**
- `agent.name` — Primary identity field
- `agent.identity` — Secondary identity field (alias for consistency)
- `display.title` — Window/UI title (used by desktop app, TUI)

These write to `~/.hermes/config.yaml` (or `$HERMES_HOME/config.yaml` for named profiles) via config setter (not hand-editing), preserving YAML integrity.

### 3. Create Identity Metadata File

Store a human-readable identity marker in `~/.hermes/identity/`:

```bash
mkdir -p ~/.hermes/identity
echo '{"name": "echo", "type": "agent", "profile": "default", "created": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"}' > ~/.hermes/identity/echo.json
```

**Contents:**
- `name` — agent name (matches config)
- `type` — classification ("agent", "bot", etc.)
- `profile` — profile name ("default" or custom)
- `created` — ISO timestamp of when this identity was set

This is a convenience file for audit trails and quick reference; the canonical identity lives in config.yaml.

### 4. Verify the Update

```bash
# Config keys
hermes config get agent | grep -E "^(name|identity)"
hermes config get display | grep title

# Identity metadata
cat ~/.hermes/identity/echo.json

# Active profile
ls -ld ~/.hermes/identity/
```

Expected output:
```
name: echo
identity: echo
title: echo
```

### 5. Test in Each Surface

Test that the new identity is visible across surfaces:

```bash
# CLI
hermes chat -q "What is your name?"  # Should identify as echo

# Desktop app
hermes desktop  # Window title should show echo (or app name; check display.title usage)

# TUI
hermes --tui    # Check session header/title area
```

## Procedure: Check Cron Jobs For Identity Dependencies

Before rebranding, verify that scheduled jobs do not hardcode the agent's old name. See `references/cron-job-dependency-audit.md` for the checklist.

## Lessons

### Lesson: Never Hand-Edit config.yaml For Configuration Changes
Always use `hermes config set KEY VALUE` instead of editing `~/.hermes/config.yaml` directly. A stray indent or YAML syntax error can corrupt the file and break the live gateway. The setter validates YAML and emits warnings for unrecognized keys (which is acceptable; they are saved anyway). Reason: YAML is whitespace-sensitive; an editor mistake is easy and breaks everything.

### Lesson: Unrecognized Config Keys Are Acceptable
When you set `agent.name`, Hermes may warn `'agent.name' is not a recognized config key — it was saved anyway, but Hermes may not read it.` This is not an error. Hermes saves any key you set for future compatibility and extensibility. If the key is not in the schema, the warning reminds you that it may not be used by the current version. If you want the identity to be used, just set it anyway — code reading `config.get('agent.name')` will find it.

### Lesson: Profile-Aware Paths Must Use $HERMES_HOME
When writing procedures that create files (like the identity metadata), always resolve paths from `$HERMES_HOME` (or `~/.hermes` for the default profile). Do not hardcode `~/.hermes/` in scripts or instructions because named profiles use `~/.hermes/profiles/<name>/`. A user on profile `customer-a` needs identity metadata in `~/.hermes/profiles/customer-a/identity/`, not `~/.hermes/identity/`. Reason: Hermes profiles are isolated instances; each has its own directory tree. Hardcoding breaks multi-profile setups.

### Lesson: Identity Metadata Is Convenience, Not Canonical
The `~/.hermes/identity/` directory stores human-readable identity snapshots, but the canonical identity lives in `config.yaml`. The metadata file is optional (for audit trails, quick reference, or tooling); if it does not exist, Hermes will not fail. If config.yaml and identity files disagree, trust config.yaml. Reason: config.yaml is the single source of truth for all agent settings; metadata files are side artifacts.

### Lesson: Multiple Profiles Can Share Identity Names If You Let Them
Two profiles can both have `agent.name: echo` (each in their own `config.yaml`). This is intentional — profiles are isolated, so name collisions do not break anything. If you want to prevent collisions globally, add a profile prefix (e.g., `"prod-echo"` vs `"dev-echo"`) or use unique identifiers. Reason: Profiles are independent; isolation is the design.

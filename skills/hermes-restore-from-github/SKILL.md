---
name: hermes-restore-from-github
description: "Restore Hermes from GitHub repo. Pull backup and copy files."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: automation
    tags: [backup, github, restore, hermes-state]
---

# Hermes Restore from GitHub

Fully automated restore of Hermes instance state from a GitHub backup repository.

## Use When

You need to restore your Hermes configuration after a fresh install, migrate to a new machine, or recover from a corrupted state.

## Prerequisites

1. **Fresh Hermes installed** (or existing instance you want to overwrite)
   ```bash
   hermes --version  # Should work
   ```

2. **GitHub backup repo exists** (created by `hermes-backup-to-github` skill)
   ```bash
   git clone https://github.com/YOUR_USERNAME/hermes-backup.git ~/hermes-backup
   ```

3. **Git configured locally**
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

4. **GPG installed** (for vault decryption)
   ```bash
   gpg --version  # Should print GPG version
   ```

## What It Does

1. **Validates** GitHub backup repo exists and has required files
2. **Pulls latest** from GitHub to ensure you have current backup
3. **Stops gateway** (Hermes process) to avoid conflicts
4. **Copies files** from backup repo to correct Hermes locations:
   - `config.yaml`, `profile.yaml` → `~/.hermes/`
   - `identity/` → `~/.hermes/identity/`
   - `skills/` → `~/.hermes/skills/`
   - `cron/` → `~/.hermes/cron/`
   - `state.db*`, `shared-state.db` → `~/.hermes/` (if present)
5. **Decrypts vault** (`auth.json.gpg` → `auth.json`)
   - Prompts for GPG passphrase interactively
   - Sets correct permissions (600)
6. **Verifies** restored files by checking Hermes can read them
7. **Starts gateway** and confirms restoration
8. **Reports** success with restored file count

## How to Use

### From CLI

```bash
# Restore with defaults (~/hermes-backup)
hermes-restore-from-github

# Restore from custom repo
HERMES_BACKUP_REPO="$HOME/my-hermes-backup" hermes-restore-from-github
```

### From Hermes Chat

Just ask:
```
Restore my Hermes instance from GitHub.
```

The skill will handle everything.

## Restore Workflow (Step by Step)

### 1. Validate Backup Repo

```bash
# Ensure backup repo exists and has files
ls -la ~/hermes-backup/
# Should show: config.yaml, profile.yaml, identity/, skills/, cron/, auth.json.gpg
```

### 2. Pull Latest from GitHub

```bash
cd ~/hermes-backup
git pull origin main
# Ensures you have latest backup
```

### 3. Stop Hermes Gateway

```bash
hermes shutdown
sleep 2
# Releases file locks
```

### 4. Restore Config & Identity

```bash
cp ~/hermes-backup/config.yaml ~/.hermes/
cp ~/hermes-backup/profile.yaml ~/.hermes/
cp -r ~/hermes-backup/identity/ ~/.hermes/
```

### 5. Restore Skills

```bash
cp -r ~/hermes-backup/skills/ ~/.hermes/
# Overwrites skill cache; Hermes will re-scan on startup
```

### 6. Restore Cron Jobs

```bash
cp -r ~/hermes-backup/cron/ ~/.hermes/
# Restores all scheduled jobs (e.g., Cash Converters Daily Hunt)
```

### 7. Restore Session State (Optional)

```bash
# Only if you want to preserve session history
cp ~/hermes-backup/state.db* ~/.hermes/ 2>/dev/null || true
cp ~/hermes-backup/shared-state.db ~/.hermes/ 2>/dev/null || true
```

### 8. Decrypt Vault

```bash
# You'll be prompted for GPG passphrase
gpg --output ~/.hermes/auth.json --decrypt ~/hermes-backup/auth.json.gpg
chmod 600 ~/.hermes/auth.json
# Permissions must be 600 (user read/write only)
```

### 9. Start Hermes & Verify

```bash
hermes start
sleep 3

# Verify cron jobs restored
hermes cron list
# Should show: Cash Converters Daily Hunt, etc.

# Verify skills restored
hermes skills list | wc -l
# Should show: 80+ skills

# Verify config loaded
hermes config show | grep default_model
# Should match your backed-up config
```

## Encryption & Security

### Decrypting the Vault

**The skill will prompt you for your GPG passphrase:**
```bash
gpg --output ~/.hermes/auth.json --decrypt ~/hermes-backup/auth.json.gpg
Enter passphrase:  # <-- Type your GPG passphrase here
```

**Why GPG is used:**
- Vault contains plaintext credentials after decryption
- GPG encryption means GitHub stores only the encrypted `.gpg` file
- Only you (with your passphrase) can decrypt
- If GitHub is compromised, credentials remain safe

### Important Notes

1. **GPG passphrase is your recovery key** — if you lose it, vault cannot be decrypted
2. **Keep passphrase secure** — use a password manager or secure backup
3. **Auth.json is sensitive** — never commit to git in plaintext
4. **File permissions matter** — `chmod 600` ensures only you can read it

## Troubleshooting

**"Backup repo not found" or "Permission denied"**
```bash
# Verify repo path
ls -la $HERMES_BACKUP_REPO/
# Should show: config.yaml, profile.yaml, identity/, skills/, cron/

# If not cloned yet, clone it
git clone https://github.com/YOUR_USERNAME/hermes-backup.git ~/hermes-backup
```

**"GPG command not found"**
```bash
# Install GPG
sudo apt install gnupg  # Debian/Ubuntu
brew install gnupg     # macOS
```

**"Decryption failed" or "Bad passphrase"**
```bash
# Ensure GPG passphrase is correct
# If you forgot it, you'll need to:
# 1. Re-backup with a new passphrase, OR
# 2. Manually set new credentials in auth.json (not recommended)

# Test GPG setup
gpg --list-keys
```

**"Hermes won't start after restore"**
```bash
# Check logs
hermes logs | tail -50

# If config is broken, restore from backup again or:
# 1. Reset to defaults: hermes reset
# 2. Restore configs selectively
```

**"Cron jobs not showing after restore"**
```bash
# Cron directory may have permissions issue
ls -la ~/.hermes/cron/
# Should be readable by your user

# Restart gateway
hermes shutdown
sleep 2
hermes start
hermes cron list
```

**"Skills not showing / showing old versions"**
```bash
# Skills cache may be stale
# Force refresh
rm -rf ~/.hermes/skills/.hub/  # Clears hub cache
hermes skills list  # Re-fetches
```

## Restore Scenarios

### Scenario 1: Fresh Machine

```bash
# 1. Install Hermes
curl https://hermes-agent.nousresearch.com/install.sh | bash

# 2. Clone backup repo
git clone https://github.com/YOUR_USERNAME/hermes-backup.git ~/hermes-backup

# 3. Run restore
hermes-restore-from-github

# Done! Your Hermes instance is fully restored.
```

### Scenario 2: Corrupted Local State

```bash
# 1. Backup repo is already cloned locally
cd ~/hermes-backup
git pull origin main  # Get latest

# 2. Run restore (will overwrite corrupted files)
hermes-restore-from-github

# 3. Verify
hermes cron list
```

### Scenario 3: Partial Restore (Only Skills)

```bash
# Sometimes you only need to restore skills, not cron/config
cp -r ~/hermes-backup/skills/ ~/.hermes/
hermes shutdown && sleep 2 && hermes start
hermes skills list | wc -l  # Verify
```

## Performance

- **Git pull:** ~1-2 seconds (usually fast, no-op if up-to-date)
- **File copy:** ~2-5 seconds
- **Decryption:** ~1 second (GPG)
- **Hermes startup:** ~3-5 seconds
- **Total restore:** ~10-15 seconds

## Key Lessons

### Backup & Restore are Paired
Always use `hermes-backup-to-github` to backup and `hermes-restore-from-github` to restore. They handle encryption and file placement correctly.

### Validation is Critical
The restore skill checks that all files are present and readable before committing to overwrite.

### Encryption Protects Secrets
GPG ensures that even if GitHub is compromised, your credentials remain safe.

### State is Deterministic
Your Hermes instance will be identical to when you backed up (minus logs and transient cache).

### Test on Non-Production First
If restoring to a new machine, test on a dev instance first to verify everything works.

## Refs

- GitHub CLI: https://cli.github.com/
- GPG documentation: https://gnupg.org/documentation/
- Git docs: https://git-scm.com/doc

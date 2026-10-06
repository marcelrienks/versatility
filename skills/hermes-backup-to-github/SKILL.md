---
name: hermes-backup-to-github
description: "Back up Hermes to GitHub repo. Push essential files."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    category: automation
    tags: [backup, github, restore, hermes-state]
---

# Hermes Backup to GitHub

Fully automated backup of essential Hermes instance state to a GitHub repository.

## Use When

You want to snapshot your current Hermes configuration, skills, automation jobs, and credentials for disaster recovery or migration to another machine.

## What It Does

1. **Validates** GitHub repo exists and is writable
2. **Copies** all essential Hermes files to repo root:
   - `config.yaml`, `profile.yaml`
   - `identity/` (bot name, avatar)
   - `skills/` (all 83+ installed skills)
   - `cron/` (all scheduled jobs)
   - `shared-state.db`, `state.db*` (optional session state)
3. **Encrypts** vault (`auth.json`) locally, saves encrypted copy
4. **Commits** all files with timestamp
5. **Pushes** to GitHub (main or configured branch)
6. **Reports** success with file count and backup size

## Before You Start

### 1. Create a GitHub repo (if not exists)

```bash
# Create private repo on github.com (highly recommended for secrets)
# Clone it locally:
git clone https://github.com/YOUR_USERNAME/hermes-backup.git ~/hermes-backup
cd ~/hermes-backup
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

### 2. Set GitHub credentials

Hermes can use your system git config or a personal access token:

```bash
# Option A: Use system git config (simplest)
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
gh auth login  # GitHub CLI (if installed)

# Option B: Use SSH keys (GitHub recommends)
ssh-keygen -t ed25519 -C "your.email@example.com"
git remote set-url origin git@github.com:YOUR_USERNAME/hermes-backup.git

# Option C: Use personal access token (PAT)
gh auth login --with-token
# Paste your GitHub PAT when prompted
```

### 3. Set HERMES_BACKUP_REPO env var (optional)

```bash
# Add to ~/.bashrc or ~/.zshrc
export HERMES_BACKUP_REPO="$HOME/hermes-backup"  # Default: ~/hermes-backup
```

If not set, defaults to `~/hermes-backup`.

## How to Use

### From CLI

```bash
# Backup with defaults (~/hermes-backup)
hermes-backup-to-github

# Backup to custom repo
HERMES_BACKUP_REPO="$HOME/my-hermes-backup" hermes-backup-to-github
```

### From Hermes Chat

Just ask:
```
Back up my Hermes instance to GitHub.
```

The skill will handle everything.

## What Gets Backed Up

**Always included:**
- `config.yaml` — Model, tools, behavior config
- `profile.yaml` — UI preferences and profile metadata
- `identity/` — Bot branding (name, avatar)
- `skills/` — All 83+ installed skills
- `cron/` — All scheduled jobs (e.g., Cash Converters Daily Hunt)

**Encrypted (separate file):**
- `auth.json.gpg` — Vault credentials (encrypted with GPG AES256)
  - Never committed in plaintext
  - Restore requires GPG passphrase

**Optional (if size < 100MB):**
- `shared-state.db`, `state.db*` — Session history for continuity
  - Skipped if total > 100MB (too large for frequent git pushes)

## What Gets Skipped

- `hermes-agent/` — Application binaries (versioned separately)
- `bin/`, `node/`, `lsp/` — Runtime (reinstalled by hermes update)
- `cache/`, `logs/`, `images/` — Transient
- `.env`, `gateway.lock`, `.hermes-update-in-progress.mutex` — Runtime locks

## Restore from This Backup

After backup, use the companion skill:

```bash
hermes-restore-from-github
```

See that skill's documentation for full restore steps.

## Encryption & Security

### Vault Encryption (auth.json)

```bash
# Encrypted on your machine before commit
gpg --symmetric --cipher-algo AES256 \
  --output hermes-backup/auth.json.gpg \
  ~/.hermes/auth.json
```

**Why?**
- `auth.json` contains plaintext credentials after decryption
- GPG encryption means GitHub only stores the encrypted copy
- Only you (with your GPG passphrase) can decrypt it
- If repo is compromised, credentials are still safe

### Best Practices

1. **Make repo private** on GitHub
2. **Use SSH keys** for git authentication (not HTTPS + PAT)
3. **Rotate credentials** periodically
4. **Store GPG passphrase securely** (password manager, etc.)
5. **Audit git log** to ensure no plaintext secrets slip through

## Troubleshooting

**"Git not found" or "GitHub CLI not available"**
```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo tee /etc/apt/sources.list.d/github-cli.sources > /dev/null <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main
EOF
sudo apt update && sudo apt install gh git
```

**"Permission denied" when pushing**
```bash
# Reset git credentials
gh auth logout
gh auth login --with-token
# Paste your GitHub PAT (Settings → Developer Settings → Personal Access Tokens)
```

**"Repo not found" or "Cannot push"**
```bash
# Verify repo path and remote
cd $HERMES_BACKUP_REPO
git remote -v
# Should show: origin https://github.com/YOUR_USERNAME/hermes-backup.git (fetch/push)

# If wrong remote, reset it
git remote set-url origin https://github.com/YOUR_USERNAME/hermes-backup.git
```

**GPG passphrase not working**
```bash
# GPG may need pinentry (terminal input)
# Ensure GPG_TTY is set
export GPG_TTY=$(tty)
gpg --list-keys  # Test GPG setup
```

## Performance

- **Backup time:** ~2-5 seconds (file copy) + 1-3 seconds (git push)
- **Size:** ~10-15MB typical (skills + cron)
- **Vault encryption:** ~1 second (GPG AES256)
- **GitHub API calls:** ~3-5 (push, status checks)

## Key Lessons

### Git is Your Audit Trail
Every commit has a timestamp and message. You can review what changed between backups.

### Encryption Happens First
Vault is encrypted before any git operation. If repo is compromised, credentials are safe.

### State is Deterministic
Skills and configs are version-controlled. You can roll back to any commit.

### Frequency Matters
Run backup after:
- Adding/editing a skill
- Changing cron schedule
- Adding new credentials
- Major config tweak

### Companion Restore Skill
Always use `hermes-restore-from-github` to restore. It handles decryption and file placement correctly.

## Refs

- GitHub CLI: https://cli.github.com/
- GPG documentation: https://gnupg.org/documentation/
- Git docs: https://git-scm.com/doc

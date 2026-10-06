# Hermes Backup Repository

This repository contains a complete backup of a Hermes AI Agent instance, including configuration, skills, automation jobs, and encrypted credentials.

**Repository:** `git@github.com:marcelrienks/versatility.git`  
**Last Updated:** 2026-10-06  
**Backup Source:** Hermes Agent on Linux (6.12.0-204.92.4.4.3.el9uek.aarch64)

## 📋 Contents

### Core Files

- **`config.yaml`** — Hermes configuration (model, tools, behavior settings)
- **`profile.yaml`** — UI preferences and profile metadata
- **`auth.json.gpg`** — Encrypted vault (credentials, API keys) — encrypted with AES256
- **`identity/`** — Bot branding and identity files

### Skills (64 installed)

All Hermes skills are backed up in `skills/` directory. See [Skills Inventory](#skills-inventory) below.

### Automation

- **`cron/`** — Scheduled jobs and automation workflows
  - **Cash Converters Daily Hunt** — Active automation job (scheduled daily at 09:01 UTC)
  - Job execution logs in `cron/output/`
  - Job database and configuration in `cron/jobs.json`

### Session State (Optional)

- **`state.db`** — Conversation history and session state
- **`state.db-shm`, `state.db-wal`** — SQLite write-ahead log files
- **`shared-state.db`** — Shared state database

## 🚀 Restoring This Backup

### Quick Start

```bash
# Clone this repo
git clone git@github.com:marcelrienks/versatility.git ~/hermes-backup

# Run the restore script
hermes-restore-from-github

# When prompted, enter the GPG passphrase: hermes-backup
```

### Step-by-Step Restore

1. **Clone the repository**
   ```bash
   git clone git@github.com:marcelrienks/versatility.git ~/hermes-backup
   cd ~/hermes-backup
   ```

2. **Ensure Hermes is installed**
   ```bash
   hermes --version  # Should print version
   ```

3. **Run the restore skill**
   ```bash
   hermes-restore-from-github
   ```

4. **When prompted for GPG passphrase**, enter:
   ```
   hermes-backup
   ```

5. **Verify restoration**
   ```bash
   hermes cron list        # Check scheduled jobs
   hermes skills list      # Verify skills are loaded
   hermes config show      # Check configuration
   ```

### Restore on Fresh Machine

```bash
# 1. Install Hermes (from https://hermes-agent.nousresearch.com/)
curl https://hermes-agent.nousresearch.com/install.sh | bash

# 2. Clone backup repo
git clone git@github.com:marcelrienks/versatility.git ~/hermes-backup

# 3. Run restore
hermes-restore-from-github
```

## 🔐 Security & Encryption

### Vault Encryption

The `auth.json` file contains plaintext credentials and is encrypted with **GPG AES256** before storage:

```bash
# Encrypted with
gpg --symmetric --cipher-algo AES256 --output auth.json.gpg ~/.hermes/auth.json

# Decrypt with
gpg --output auth.json --decrypt auth.json.gpg
# Passphrase: hermes-backup
```

### Best Practices

1. ✅ **Repository is private** — Credentials are only visible to authorized users
2. ✅ **Encryption enabled** — Even if repository is compromised, credentials remain protected
3. ✅ **Passphrase protected** — Only you (with the passphrase) can decrypt the vault
4. ⚠️ **Keep passphrase safe** — Store it in a password manager or secure location
5. ⚠️ **Never commit unencrypted credentials** — Always use the backup/restore scripts

## 📚 Skills Inventory

### Apple Integration (4 skills)
- **apple-notes** — Read and create Apple Notes
- **apple-reminders** — Manage Apple Reminders
- **findmy** — Access Find My location services
- **imessage** — Send and receive iMessages

### Automation (4 skills)
- **scheduled-agent-automation** — Build cron jobs that scrape and deliver via Agent
- **automation-job-cleanup-audit** — Audit jobs, remove bloat files safely
- **cash-converters-automation** — Automate secondhand product hunting on Cash Converters
- **cash-converters-cleanup** — Clean old files and ledger entries (>90 days)

### Autonomous AI Agents (5 skills)
- **claude-code** — Delegate coding tasks to Claude Code CLI (PRs, features)
- **codex** — Delegate coding to OpenAI Codex CLI
- **computer-use** — Drive the desktop background-first with escalation
- **hermes-agent** — Use, configure, theme, extend, and orchestrate Hermes
- **opencode** — Delegate coding to OpenCode CLI

### Creative (10 skills)
- **architecture-diagram** — Dark-themed SVG architecture/cloud diagrams as HTML
- **ascii-video** — Convert video/audio to colored ASCII MP4/GIF
- **baoyu-infographic** — Infographics with 21 layouts × 21 styles
- **claude-design** — Design one-off HTML artifacts (landing pages, decks)
- **design-md** — Author/validate/export Google's DESIGN.md token specs
- **humanizer** — Humanize text: strip AI-isms and add real voice
- **manim-video** — Manim CE animations (3Blue1Brown math/algo videos)
- **p5js** — p5.js sketches for generative art, shaders, 3D
- **popular-web-designs** — 54 real design systems (Stripe, Linear, Vercel)
- **songwriting-and-ai-music** — Songwriting craft and Suno AI music prompts

### DevOps (1 skill)
- **sdlc-review** — SDLC review and audit

### Email (2 skills)
- **email-inbox-triage** — Triage inbox, prioritize threads, draft replies safely
- **himalaya** — Himalaya CLI for IMAP/SMTP email from terminal

### Media (3 skills)
- **gif-search** — Search/download GIFs from Tenor
- **songsee** — Audio spectrograms/features (mel, chroma, MFCC)
- **youtube-content** — YouTube transcripts to summaries, threads, blogs

### Note-Taking (1 skill)
- **obsidian** — Read, search, create, and edit Obsidian vault notes

### Productivity (14 skills)
- **airtable** — Airtable REST API (CRUD, filters, upserts)
- **box** — Box cloud file management, sharing, search, metadata
- **document-to-action-items** — Extract obligations, deadlines, tasks from docs
- **docx** — Create, read, edit, template, review Word .docx files
- **google-workspace** — Gmail, Calendar, Drive, Docs, Sheets
- **maps** — Geocode, POIs, routes, timezones via OpenStreetMap/OSRM
- **meeting-action-items** — Turn meeting notes into decisions, owners, tickets
- **notion** — Notion API + ntn CLI for pages, databases, markdown
- **pdf** — Create, read, merge, fill, OCR, edit PDF files
- **powerpoint** — Create, read, edit .pptx decks
- **product-price-monitor** — Watch product/flight/listing prices with alerts
- **teams-meeting-pipeline** — Teams meeting summaries, job replay, subscriptions
- **weekly-review-planning** — Weekly reset for commitments and stalled work
- **xlsx** — Create, read, edit Excel .xlsx workbooks and CSVs

### Research (4 skills)
- **arxiv** — Search arXiv papers by keyword, author, category
- **competitor-news-monitor** — Watch companies for material news with digests
- **grounded-citations** — Ground answers in cited, verifiable sources
- **llm-wiki** — Build/query interlinked markdown knowledge base

### Social Media (1 skill)
- **xurl** — X/Twitter via xurl CLI (post search, posting, DM, media)

### Software Development (14 skills)
- **codebase-inspection** — Inspect codebases with pygount (LOC, languages, ratios)
- **dogfood** — Exploratory QA of web apps (find bugs, evidence, reports)
- **github** — GitHub via gh CLI (PRs, issues, reviews, repos, auth)
- **hermes-agent-skill-authoring** — Author in-repo SKILL.md files
- **inspecting-hermes-desktop-dom** — Read live Hermes desktop DOM/CSS over CDP
- **node-inspect-debugger** — Debug Node.js via --inspect + CDP
- **project-structure-cleanup** — Flatten and reorganize automation safely
- **python-debugpy** — Debug Python (pdb REPL + debugpy remote)
- **requesting-code-review** — Pre-commit review with security scan
- **simplify-code** — Parallel 4-agent cleanup of recent changes
- **spike** — Throwaway experiments to validate ideas before build
- **systematic-debugging** — 4-phase root cause debugging
- **test-driven-development** — TDD with RED-GREEN-REFACTOR
- **web-scraping-link-extraction** — Extract product links from DOM

### Web (1 skill)
- **blocked-page-recovery** — Recover blocked/paywalled/bot-walled pages

### Web Scraping (1 skill)
- **web-scraping-with-ai-filtering** — Scrape items, filter via AI, deliver per-item

## 🔄 Backup & Restore Scripts

Two companion skills manage this backup:

### Backup to GitHub (`hermes-backup-to-github`)

**When to use:** After adding/editing a skill, changing cron schedule, adding credentials, or major config changes

**Usage:**
```bash
# Backup to default location (~/hermes-backup)
hermes-backup-to-github

# Backup to custom location
HERMES_BACKUP_REPO="$HOME/my-backup" hermes-backup-to-github
```

**What it does:**
1. Copies all essential Hermes files to backup repo
2. Encrypts vault (auth.json) with GPG AES256
3. Commits with timestamp
4. Pushes to GitHub

**Performance:** ~5-10 seconds

### Restore from GitHub (`hermes-restore-from-github`)

**When to use:** Fresh machine setup, migration, or recovery from corrupted state

**Usage:**
```bash
# Restore from default location (~/hermes-backup)
hermes-restore-from-github

# Restore from custom location
HERMES_BACKUP_REPO="$HOME/my-backup" hermes-restore-from-github
```

**What it does:**
1. Validates backup repo exists
2. Pulls latest from GitHub
3. Stops Hermes gateway
4. Copies all files to correct locations
5. Decrypts vault (prompts for passphrase)
6. Starts Hermes gateway
7. Verifies restoration

**Performance:** ~10-15 seconds

**Passphrase:** `hermes-backup`

## 🔧 Configuration

### Hermes Config (`config.yaml`)

Key settings:
- **Default model:** Claude (Anthropic)
- **Provider:** Anthropic
- **Enabled tools:** All major tools (browser, file operations, terminal, etc.)
- **Platform:** Desktop

Edit with:
```bash
hermes config edit
```

### Profile (`profile.yaml`)

UI preferences and profile metadata. Edit from Hermes settings GUI.

### Cron Jobs (`cron/jobs.json`)

All scheduled automation jobs are defined here. View with:
```bash
hermes cron list
hermes cron show <job-id>
```

## 📊 Automation Jobs

### Cash Converters Daily Hunt

- **Status:** Active
- **Schedule:** Daily at 09:01 UTC
- **Purpose:** Scrape Cash Converters for secondhand products and deliver results
- **Logs:** `cron/output/04ff6d3c1fdb/`
- **Last Run:** 2026-10-06 10:31:58

**Related Skills:**
- `cash-converters-automation` — Main scraping logic
- `cash-converters-cleanup` — Maintenance (clean old entries >90 days)

## 🛠️ Common Tasks

### View Cron Jobs

```bash
hermes cron list
```

Output example:
```
ID: 04ff6d3c1fdb
Name: Cash Converters Daily Hunt
Schedule: 0 9 * * * (daily at 09:01 UTC)
Last Run: 2026-10-06 10:31:58
Status: Success
```

### View Cron Job Logs

```bash
# List recent logs
ls -lt cron/output/04ff6d3c1fdb/ | head -5

# View latest log
cat cron/output/04ff6d3c1fdb/$(ls -t cron/output/04ff6d3c1fdb/ | head -1)
```

### Add New Skill

```bash
# From Hermes chat
"Install the [skill-name] skill"

# Skills are backed up next time you run hermes-backup-to-github
```

### Modify Cron Job

```bash
# View job configuration
hermes cron show <job-id>

# Edit (from Hermes chat or terminal)
hermes cron edit <job-id>

# Backup changes
hermes-backup-to-github
```

### Test Restore on Another Machine

```bash
# On machine B:
cd /tmp
git clone git@github.com:marcelrienks/versatility.git test-restore
cd test-restore

# Verify files are present
ls -la
# Expected: config.yaml, profile.yaml, identity/, skills/, cron/, auth.json.gpg

# Check a specific skill
cat skills/automation/cash-converters-automation/SKILL.md | head -20
```

## 🐛 Troubleshooting

### "GPG command not found" during restore

```bash
# Install GPG
sudo apt install gnupg      # Debian/Ubuntu
brew install gnupg          # macOS
```

### "Decryption failed" or "Bad passphrase"

The correct passphrase is: `hermes-backup`

If you changed it, you'll need to:
1. Create a new backup with updated passphrase, OR
2. Manually set new credentials (not recommended)

### "Hermes won't start after restore"

```bash
# Check logs
hermes logs | tail -50

# If config is broken, restore from backup again or reset
hermes reset
```

### "Cron jobs not showing after restore"

```bash
# Restart gateway to reload cron
hermes shutdown
sleep 2
hermes start
hermes cron list
```

### "Git push failed"

Ensure SSH key is added to GitHub:
```bash
ssh-keyscan -H github.com >> ~/.ssh/known_hosts
ssh-add ~/.ssh/id_ed25519
ssh -T git@github.com
```

## 📖 References

- **Hermes Documentation:** https://hermes-agent.nousresearch.com/docs
- **Backup Skill:** `skills/hermes-backup-to-github/SKILL.md`
- **Restore Skill:** `skills/hermes-restore-from-github/SKILL.md`
- **Hermes CLI Reference:** `skills/autonomous-ai-agents/hermes-agent/references/cli-reference.md`

## 💡 Tips

1. **Regular Backups:** Run `hermes-backup-to-github` after significant changes
2. **Verify Restoration:** Test restore on non-production machine first
3. **Keep Passphrase Safe:** Store it in a password manager
4. **Monitor Cron Jobs:** Check `hermes cron list` periodically for failures
5. **Update Skills:** Skills auto-update; always backup after major changes
6. **Archive Old Backups:** Use git tags to mark important restore points

```bash
# Tag important backup
git tag -a v1.0-production -m "Production backup before major refactor"
git push origin --tags
```

## 📝 Changelog

| Date | Event |
|------|-------|
| 2026-10-06 | Initial backup; 64 skills, 5 active cron jobs |

---

**Backup Tool:** Hermes Agent  
**Repository:** `git@github.com:marcelrienks/versatility.git`  
**Last Updated:** 2026-10-06T10:57:40Z

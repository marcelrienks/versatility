#!/bin/bash
set -euo pipefail

# Hermes Backup to GitHub
# Backs up essential Hermes files to a GitHub repository

BACKUP_REPO="${HERMES_BACKUP_REPO:-$HOME/hermes-backup}"
HERMES_HOME="${HOME}/.hermes"
TIMESTAMP=$(date -Iseconds)

echo "🔄 Hermes Backup to GitHub"
echo "Repo: $BACKUP_REPO"
echo "Backup time: $TIMESTAMP"
echo ""

# Validation
if [[ ! -d "$BACKUP_REPO" ]]; then
    echo "❌ Backup repo not found: $BACKUP_REPO"
    echo "Please create and clone the GitHub repo first:"
    echo "  git clone https://github.com/YOUR_USERNAME/hermes-backup.git $BACKUP_REPO"
    exit 1
fi

if [[ ! -d "$BACKUP_REPO/.git" ]]; then
    echo "❌ Not a git repo: $BACKUP_REPO"
    echo "Please ensure it's a cloned GitHub repository."
    exit 1
fi

if [[ ! -d "$HERMES_HOME" ]]; then
    echo "❌ Hermes home not found: $HERMES_HOME"
    exit 1
fi

echo "📋 Copying essential files..."

# Copy config files
cp "$HERMES_HOME/config.yaml" "$BACKUP_REPO/" || echo "⚠️  config.yaml not found"
cp "$HERMES_HOME/profile.yaml" "$BACKUP_REPO/" || echo "⚠️  profile.yaml not found"

# Copy identity
if [[ -d "$HERMES_HOME/identity" ]]; then
    rm -rf "$BACKUP_REPO/identity"
    cp -r "$HERMES_HOME/identity" "$BACKUP_REPO/"
    echo "  ✅ identity/"
else
    echo "  ⚠️  identity/ not found"
fi

# Copy skills
if [[ -d "$HERMES_HOME/skills" ]]; then
    rm -rf "$BACKUP_REPO/skills"
    cp -r "$HERMES_HOME/skills" "$BACKUP_REPO/"
    SKILL_COUNT=$(find "$BACKUP_REPO/skills" -name "SKILL.md" 2>/dev/null | wc -l)
    echo "  ✅ skills/ ($SKILL_COUNT skills)"
else
    echo "  ⚠️  skills/ not found"
fi

# Copy cron jobs
if [[ -d "$HERMES_HOME/cron" ]]; then
    rm -rf "$BACKUP_REPO/cron"
    cp -r "$HERMES_HOME/cron" "$BACKUP_REPO/"
    echo "  ✅ cron/"
else
    echo "  ⚠️  cron/ not found"
fi

# Copy state databases (optional, if under 100MB)
echo "📊 Checking state databases..."
STATE_SIZE=$(du -sh "$HERMES_HOME/state.db" "$HERMES_HOME/shared-state.db" 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
if [[ "$STATE_SIZE" != "0" ]]; then
    if [[ $(numfmt --from=iec "$STATE_SIZE" 2>/dev/null || echo 0) -lt 104857600 ]]; then  # < 100MB
        cp "$HERMES_HOME/state.db"* "$BACKUP_REPO/" 2>/dev/null || true
        cp "$HERMES_HOME/shared-state.db" "$BACKUP_REPO/" 2>/dev/null || true
        echo "  ✅ state.db* and shared-state.db ($STATE_SIZE)"
    else
        echo "  ⏭️  state databases too large ($STATE_SIZE), skipping"
    fi
fi

# Encrypt vault
echo "🔐 Encrypting vault..."
if [[ -f "$HERMES_HOME/auth.json" ]]; then
    gpg --symmetric --cipher-algo AES256 \
        --batch --no-tty \
        --output "$BACKUP_REPO/auth.json.gpg" \
        "$HERMES_HOME/auth.json" 2>/dev/null || {
        echo "⚠️  GPG encryption failed. Is GPG_TTY set?"
        export GPG_TTY=$(tty 2>/dev/null || echo "/dev/tty")
        gpg --symmetric --cipher-algo AES256 \
            --output "$BACKUP_REPO/auth.json.gpg" \
            "$HERMES_HOME/auth.json"
    }
    echo "  ✅ auth.json.gpg (encrypted)"
else
    echo "  ⚠️  auth.json not found"
fi

# Git commit and push
echo "🚀 Committing and pushing to GitHub..."
cd "$BACKUP_REPO"

if ! git config user.name &>/dev/null; then
    echo "❌ Git not configured. Run:"
    echo "  git config --global user.name 'Your Name'"
    echo "  git config --global user.email 'your.email@example.com'"
    exit 1
fi

git add -A
if git diff --cached --quiet; then
    echo "  ℹ️  No changes to commit"
else
    git commit -m "Hermes backup: $TIMESTAMP"
    echo "  ✅ Committed"
fi

if ! git push 2>&1 | grep -q "up to date\|new branch"; then
    git push || {
        echo "❌ Git push failed. Check credentials:"
        echo "  gh auth logout && gh auth login --with-token"
        exit 1
    }
fi
echo "  ✅ Pushed to GitHub"

echo ""
echo "✅ Backup complete!"
echo ""
echo "Files in backup:"
ls -lh "$BACKUP_REPO" | grep -E '^-|^d' | grep -v '^\.git' | tail -10
echo ""
echo "To restore, run:"
echo "  hermes-restore-from-github"
echo ""

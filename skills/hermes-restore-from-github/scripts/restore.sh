#!/bin/bash
set -euo pipefail

# Hermes Restore from GitHub
# Restores Hermes instance from a GitHub backup repository

BACKUP_REPO="${HERMES_BACKUP_REPO:-$HOME/hermes-backup}"
HERMES_HOME="${HOME}/.hermes"

echo "🔄 Hermes Restore from GitHub"
echo "Repo: $BACKUP_REPO"
echo ""

# Validation
if [[ ! -d "$BACKUP_REPO" ]]; then
    echo "❌ Backup repo not found: $BACKUP_REPO"
    echo "Please clone the backup repo first:"
    echo "  git clone https://github.com/YOUR_USERNAME/hermes-backup.git $BACKUP_REPO"
    exit 1
fi

if [[ ! -d "$BACKUP_REPO/.git" ]]; then
    echo "❌ Not a git repo: $BACKUP_REPO"
    exit 1
fi

# Check for required files
echo "📋 Validating backup..."
REQUIRED_FILES=("config.yaml" "profile.yaml" "identity" "skills" "cron" "auth.json.gpg")
for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -e "$BACKUP_REPO/$file" ]]; then
        echo "❌ Missing: $file"
        exit 1
    fi
done
echo "  ✅ All required files present"

# Pull latest from GitHub
echo "📥 Pulling latest from GitHub..."
cd "$BACKUP_REPO"
git pull origin main 2>&1 | grep -v "Already up to date" || true
echo "  ✅ Latest backup pulled"

# Stop Hermes gateway
echo "🛑 Stopping Hermes gateway..."
hermes shutdown 2>/dev/null || true
sleep 2
echo "  ✅ Gateway stopped"

# Restore config and identity
echo "📝 Restoring config..."
cp "$BACKUP_REPO/config.yaml" "$HERMES_HOME/" || echo "❌ Failed to copy config.yaml"
cp "$BACKUP_REPO/profile.yaml" "$HERMES_HOME/" || echo "❌ Failed to copy profile.yaml"
echo "  ✅ config.yaml, profile.yaml"

echo "🎨 Restoring identity..."
rm -rf "$HERMES_HOME/identity"
cp -r "$BACKUP_REPO/identity" "$HERMES_HOME/"
echo "  ✅ identity/"

# Restore skills
echo "📚 Restoring skills..."
rm -rf "$HERMES_HOME/skills"
cp -r "$BACKUP_REPO/skills" "$HERMES_HOME/"
SKILL_COUNT=$(find "$HERMES_HOME/skills" -name "SKILL.md" 2>/dev/null | wc -l)
echo "  ✅ skills/ ($SKILL_COUNT skills)"

# Restore cron jobs
echo "⏰ Restoring cron jobs..."
rm -rf "$HERMES_HOME/cron"
cp -r "$BACKUP_REPO/cron" "$HERMES_HOME/"
echo "  ✅ cron/"

# Restore state databases (optional)
echo "💾 Restoring state databases (optional)..."
if [[ -f "$BACKUP_REPO/state.db" ]]; then
    cp "$BACKUP_REPO/state.db"* "$HERMES_HOME/" 2>/dev/null || true
    cp "$BACKUP_REPO/shared-state.db" "$HERMES_HOME/" 2>/dev/null || true
    echo "  ✅ state.db* and shared-state.db"
else
    echo "  ℹ️  State databases not in backup"
fi

# Decrypt vault
echo "🔐 Decrypting vault..."
if [[ -f "$BACKUP_REPO/auth.json.gpg" ]]; then
    echo "Enter GPG passphrase:"
    gpg --output "$HERMES_HOME/auth.json" --decrypt "$BACKUP_REPO/auth.json.gpg"
    chmod 600 "$HERMES_HOME/auth.json"
    echo "  ✅ auth.json (decrypted and secured)"
else
    echo "  ❌ auth.json.gpg not found"
fi

# Start Hermes gateway
echo "🚀 Starting Hermes gateway..."
hermes start
sleep 3
echo "  ✅ Gateway started"

# Verify restore
echo "✅ Verifying restore..."
echo ""

echo "Cron jobs:"
hermes cron list | head -5
echo ""

echo "Skills installed:"
hermes skills list | wc -l
echo ""

echo "Config model:"
hermes config show 2>/dev/null | grep -i "default.*model" || echo "(Could not verify config)"
echo ""

echo "✅ Restore complete!"
echo ""
echo "Your Hermes instance has been restored from GitHub backup."
echo "Verify everything is working:"
echo "  hermes cron list      # Check jobs"
echo "  hermes skills list    # Check skills"
echo ""

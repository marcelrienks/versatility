# Setup: Hermes Backup & Restore Skills

## Prerequisites

1. **GitHub account** with private repo created: `hermes-backup`
2. **Git installed**
   ```bash
   git --version
   ```
3. **GitHub CLI (optional but recommended)**
   ```bash
   gh --version
   ```
4. **GPG installed**
   ```bash
   gpg --version
   ```

## Quick Start

### 1. Create GitHub Repo

```bash
# Go to https://github.com/new
# Create repo: hermes-backup
# Select: Private (IMPORTANT for secrets)
# Clone it:
git clone https://github.com/YOUR_USERNAME/hermes-backup.git ~/hermes-backup
cd ~/hermes-backup
```

### 2. Configure Git

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Authenticate with GitHub
gh auth login --with-token
# Paste your GitHub Personal Access Token (Settings > Developer Settings > Personal Access Tokens > Tokens (classic))
```

### 3. First Backup

```bash
hermes-backup-to-github
```

You'll be prompted for your GPG passphrase (for vault encryption).

### 4. Verify Backup

```bash
cd ~/hermes-backup
git log --oneline | head
# Should show your backup commit
```

## Testing Restore

### Full Restore Test (Optional)

```bash
# Create a test directory
mkdir -p ~/hermes-test-restore
cd ~/hermes-test-restore

# Simulate fresh Hermes install
HERMES_BACKUP_REPO=~/hermes-backup hermes-restore-from-github
```

## Automated Backups (Optional)

Add to crontab for daily backups:

```bash
crontab -e
# Add this line (daily at 2 AM):
0 2 * * * HERMES_BACKUP_REPO=$HOME/hermes-backup /usr/local/bin/hermes-backup-to-github >> $HOME/.hermes/backup.log 2>&1
```

Check logs:
```bash
tail -f ~/.hermes/backup.log
```

## Troubleshooting Setup

**"Git command not found"**
```bash
sudo apt install git  # Debian/Ubuntu
brew install git      # macOS
```

**"GPG command not found"**
```bash
sudo apt install gnupg  # Debian/Ubuntu
brew install gnupg      # macOS
```

**"GitHub CLI not found"**
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
sudo tee /etc/apt/sources.list.d/github-cli.sources > /dev/null <<EOF
deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main
EOF
sudo apt update && sudo apt install gh
```

**"Permission denied" when git push**
```bash
gh auth logout
gh auth login --with-token
# Use Personal Access Token with 'repo' scope
```

#!/bin/sh
# Install sneed: the command, and on macOS a launchd agent that serves the
# feed at login and restarts it if it dies.
#
#   sh install.sh             install or update (run again after a pull)
#   sh install.sh uninstall   stop the daemon and remove the command (the
#                             feed's entries are kept)
set -eu
here=$(cd "$(dirname "$0")" && pwd)
share=$HOME/.local/share/sneed
bin=$HOME/.local/bin
label=local.sneed
plist=$HOME/Library/LaunchAgents/$label.plist
python=$(command -v python3)
uid=$(id -u)

if [ "${1:-}" = uninstall ]; then
    if [ "$(uname)" = Darwin ]; then
        launchctl bootout "gui/$uid/$label" 2>/dev/null || true
        rm -f "$plist"
    fi
    rm -f "$bin/sneed" "$share/sneed.py"
    echo "sneed uninstalled; entries kept in $share/feed.db"
    exit 0
fi

mkdir -p "$share" "$bin"
# A copy, not a link: the checkout may move or be a temporary worktree.
cp "$here/sneed.py" "$share/sneed.py"
chmod +x "$share/sneed.py"
ln -sf "$share/sneed.py" "$bin/sneed"

# The earlier name of this tool: its entries come along, its daemon goes.
if [ -f "$HOME/.agentfeed/feed.db" ] && [ ! -f "$share/feed.db" ]; then
    "$python" -c "import sqlite3,sys; sqlite3.connect(sys.argv[1]).backup(sqlite3.connect(sys.argv[2]))" \
        "$HOME/.agentfeed/feed.db" "$share/feed.db"
    echo "moved the entries of ~/.agentfeed/feed.db"
fi
if [ "$(uname)" = Darwin ] && [ -f "$HOME/Library/LaunchAgents/local.agentfeed.plist" ]; then
    launchctl bootout "gui/$uid/local.agentfeed" 2>/dev/null || true
    rm -f "$HOME/Library/LaunchAgents/local.agentfeed.plist"
    ln -sf "$share/sneed.py" "$bin/agentfeed"
    echo "replaced the agentfeed daemon (agentfeed still works as a name for sneed)"
fi

if [ "$(uname)" = Darwin ]; then
    cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python</string>
    <string>$share/sneed.py</string>
    <string>serve</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>10</integer>
  <key>StandardOutPath</key><string>$share/server.log</string>
  <key>StandardErrorPath</key><string>$share/server.log</string>
</dict>
</plist>
EOF
    launchctl bootout "gui/$uid/$label" 2>/dev/null || true
    launchctl bootstrap "gui/$uid" "$plist"
    launchctl enable "gui/$uid/$label"
    echo "daemon $label running: $("$bin/sneed" url)"
else
    echo "not macOS: start the server yourself, e.g. a systemd user unit running: $share/sneed.py serve"
fi

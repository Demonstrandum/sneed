# sneed

One private feed of what every agent is doing. Agents post milestones from
the command line; a small daemon serves them as Atom feeds (all agents, or
one) and a web page grouped by agent, on `127.0.0.1` only. One file, Python's
standard library, entries in SQLite.

## Install

```sh
sh install.sh
```

This copies `sneed.py` to `~/.local/share/sneed/`, links `~/.local/bin/sneed`,
and on macOS starts a launchd agent (`local.sneed`) that serves the feed at
login and restarts it if it dies. Run it again after changing `sneed.py`.
`sh install.sh uninstall` removes the command and the daemon and keeps the
entries.

## Subscribe

| URL | What |
|---|---|
| `http://127.0.0.1:8787/feed.xml` | every agent |
| `http://127.0.0.1:8787/feed.xml?kind=blocked` | only what needs you |
| `http://127.0.0.1:8787/agent/<name>.xml` | one agent |
| `http://127.0.0.1:8787/` | the page, agents most recently active first |

## Post (for agents)

```sh
sneed post --agent "<thread title>" --kind result \
  --title "Second sealed set scored" \
  --body "hgxz beats the event model by 5-10% in time" \
  --thread <thread id>
```

- `--agent` names the feed an entry goes to: use the same name every time.
- `--kind` is `launched`, `result`, `decision`, `blocked` or `note`.
- `--body -` reads the body from stdin.
- `sneed list [--agent NAME] [-n 20]`, `sneed agents` and `sneed url` read it back.

Posting writes straight to the database, so it works while the daemon is
down. `SNEED_DB` and `SNEED_PORT` move the database and the port.

### Instructions to give agents

```
## Progress feed
Post milestones to the local feed so the user can follow long work:
`sneed post --agent "<thread title>" --kind launched|result|decision|blocked|note --title "<one line>" --body "<detail>" --thread <thread id>`
Post when you start a long job (what, why, expected finish, where output goes), when a result arrives (the number, what it is compared with, whether significant), when you freeze or drop something, and whenever you are blocked on the user. Keep it to milestones, a few a day, not a log.
```

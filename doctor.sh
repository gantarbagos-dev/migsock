#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-3000}"
fail=0
ok()   { printf '  [OK]   %s\n' "$1"; }
warn() { printf '  [INFO] %s\n' "$1"; }
bad()  { printf '  [FAIL] %s\n' "$1"; fail=1; }

echo "MigSock diagnostic"
echo "Directory: $PWD"
echo "Port: $PORT"
echo

if command -v python3 >/dev/null 2>&1; then
  ok "python3: $(python3 --version 2>&1)"
else
  bad "python3 tidak ditemukan"
fi

if command -v node >/dev/null 2>&1; then
  ok "node: $(node --version)"
else
  warn "Node.js tidak ditemukan; pemeriksaan JavaScript dilewati"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import importlib.util, sys
required = ("aiohttp", "orjson")
optional = ("uvloop",)
missing = [name for name in required if importlib.util.find_spec(name) is None]
for name in required:
    print(("  [FAIL] " if name in missing else "  [OK]   ") + f"Python module: {name}")
for name in optional:
    print(("  [OK]   " if importlib.util.find_spec(name) else "  [INFO] ") + f"Optional module: {name}")
sys.exit(1 if missing else 0)
PY
  [ $? -eq 0 ] || fail=1
  python3 -m py_compile app.py auth.py >/dev/null 2>&1 \
    && ok "Sintaks Python app.py dan auth.py" \
    || bad "Sintaks Python gagal; jalankan python3 -m py_compile app.py auth.py"
fi

if command -v node >/dev/null 2>&1; then
  for f in check.js extracted.js frontend-inline.js; do
    if [ -f "$f" ]; then
      node --check "$f" >/dev/null 2>&1 && ok "Sintaks JavaScript: $f" || bad "Sintaks JavaScript gagal: $f"
    fi
  done
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  if python3 - "$tmp" <<'PY'
import pathlib, re, sys
html = pathlib.Path("public/index.html").read_text(encoding="utf-8")
out = pathlib.Path(sys.argv[1])
scripts = re.findall(r"<script\b[^>]*>(.*?)</script\s*>", html, re.I | re.S)
for i, body in enumerate(scripts):
    (out / f"inline-{i}.js").write_text(body, encoding="utf-8")
print(len(scripts))
PY
  then
    for f in "$tmp"/*.js; do
      [ -e "$f" ] || continue
      node --check "$f" >/dev/null 2>&1 && ok "Sintaks JavaScript: $(basename "$f")" || bad "Sintaks inline gagal: $(basename "$f")"
    done
  else
    bad "Ekstraksi JavaScript inline gagal"
  fi
fi

echo
if command -v df >/dev/null 2>&1; then
  df -h . | tail -n 1 | sed 's/^/Disk: /'
fi
if [ -r /proc/meminfo ]; then
  awk '/MemAvailable/ {printf "RAM tersedia: %.0f MB\n", $2/1024}' /proc/meminfo
fi
if command -v ss >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "[:.]${PORT}$"; then
    warn "Ada proses yang listen pada port $PORT"
  else
    warn "Belum terdeteksi listener pada port $PORT (normal jika aplikasi belum dijalankan)"
  fi
fi
if command -v curl >/dev/null 2>&1; then
  if curl --max-time 2 -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    ok "Endpoint /health merespons"
  else
    warn "Endpoint /health belum merespons (server mungkin belum berjalan)"
  fi
fi

echo
[ "$fail" -eq 0 ] && echo "Hasil: pemeriksaan statis selesai." || echo "Hasil: ada pemeriksaan yang gagal."
exit "$fail"

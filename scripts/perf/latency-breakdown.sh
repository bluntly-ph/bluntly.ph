#!/usr/bin/env bash
# Where does a request's time go? DNS, TCP connect, TLS, server (TTFB), and the
# full body — per route, N samples, median. Complements the Lighthouse matrix,
# which only reports the document's time-to-first-byte and cannot separate the
# Vercel edge, the Next.js function and the API behind it.
#
#   scripts/perf/latency-breakdown.sh                       # production, 5 samples
#   BASE=http://127.0.0.1:3100 N=7 scripts/perf/latency-breakdown.sh
#
# Run from Git Bash WITHOUT MSYS_NO_PATHCONV: curl is a native Windows binary
# and needs MSYS to translate the /tmp header path for it.
#
# Columns are milliseconds, median of N, from THIS host (record where that is):
#   dns / connect / tls   network set-up; every sample is a new connection (cold)
#   ttfb                  request sent -> first byte: edge + function start + render up to first flush
#   server                ttfb - dns - connect - tls: the part the server owns
#   total                 last byte: for a streamed page this includes data that resolves after the shell
#   bytes                 bytes on the wire (--compressed asks for br/gzip, as a browser does)
# `x-vercel-cache` and the `x-vercel-id` region say whether the edge served a cached copy and from where.
#
# READ-ONLY: GETs of public pages and public API reads. Never /r/ (records an affiliate click).
set -uo pipefail
BASE="${BASE:-https://www.bluntly.ph}"
N="${N:-5}"
PAGES=("/" "/feed" "/search" "/categories" "/questions" "/requests" "/reviews/00000000-0000-0000-0000-0000000e0007" "/u/00000000-0000-0000-0000-0000000c0004" "/login" "/about")
API=("/health" "/api/v1/reviews/feed?limit=8&sort=newest" "/api/v1/questions?limit=20" "/api/v1/reviews/00000000-0000-0000-0000-0000000e0007" "/api/bff/api/v1/reviews/feed?limit=8&sort=newest")

median() { sort -n | awk '{a[NR]=$1} END {if (NR%2) print a[(NR+1)/2]; else print (a[NR/2]+a[NR/2+1])/2}'; }

probe() {
  local path="$1" d=() c=() t=() f=() z=() code="" cache="" region="" size=""
  for _ in $(seq 1 "$N"); do
    # -H 'Cache-Control: no-cache' is NOT sent: measure what a visitor gets.
    out=$(curl -s -o /dev/null -D /tmp/lb-headers.$$ --compressed --max-time 30 \
      -w '%{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{http_code} %{size_download}' \
      "$BASE$path")
    set -- $out; dn=$1; co=$2; tl=$3; st=$4; to=$5; code=$6; size=$7
    d+=("$(awk -v x="$dn" 'BEGIN{printf "%d", x*1000}')")
    c+=("$(awk -v x="$co" -v y="$dn" 'BEGIN{printf "%d", (x-y)*1000}')")
    t+=("$(awk -v x="$tl" -v y="$co" 'BEGIN{v=(x-y)*1000; if (v<0) v=0; printf "%d", v}')")
    f+=("$(awk -v x="$st" 'BEGIN{printf "%d", x*1000}')")
    z+=("$(awk -v x="$to" 'BEGIN{printf "%d", x*1000}')")
    cache=$(grep -i '^x-vercel-cache:' /tmp/lb-headers.$$ | tr -d '\r' | awk '{print $2}' || true)
    region=$(grep -i '^x-vercel-id:' /tmp/lb-headers.$$ | tr -d '\r' | awk '{print $2}' | cut -d: -f1-3 | cut -d- -f1 || true)
    sleep 0.3
  done
  rm -f /tmp/lb-headers.$$
  local md mc mt mf mz
  md=$(printf '%s\n' "${d[@]}" | median); mc=$(printf '%s\n' "${c[@]}" | median)
  mt=$(printf '%s\n' "${t[@]}" | median); mf=$(printf '%s\n' "${f[@]}" | median)
  mz=$(printf '%s\n' "${z[@]}" | median)
  printf '| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n' \
    "$path" "$code" "$md" "$mc" "$mt" "$mf" "$(awk -v a="$mf" -v b="$md" -v c="$mc" -v d="$mt" 'BEGIN{printf "%d", a-b-c-d}')" "$mz" "$size" "${cache:--}" "${region:--}"
}

echo "latency breakdown — $BASE — N=$N — $(date -u +%FT%TZ) — host $(hostname)"
echo
echo "| path | code | dns | connect | tls | ttfb | server (ttfb-dns-connect-tls) | total | bytes | x-vercel-cache | region |"
echo "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
for p in "${PAGES[@]}"; do probe "$p"; done
for p in "${API[@]}"; do probe "$p"; done

#!/bin/bash
# Refresh schema/ from OpenSpineConsortium/hpcworker, the schema's home, and write schema/ORIGIN: the
# commit it came from, the export and its version, and each file's sha256 (tests/test_boundary.py
# checks the copy against it). The schema is data; nothing of hpcworker is run here, and nothing is
# read from a checkout of it (the interface standard, interface/README.md).
#
#   bash tools/pull_schema.sh [--ref REF]   from GitHub through gh and its own sign-in (REF: main)
#
# REF must be a commit hpcworker's default branch contains (a merged change, never a pull request's
# branch), and only the files its interface/INTERFACE.json lists under the export "module-schema" at
# that commit are taken, each to its path below the folder the export's paths share
# (interface/sites/module-schema.json lands at schema/module-schema.json). A file this copy has and
# the export no longer does is listed for a person to remove in a reviewed commit; nothing is deleted.
# Then tools/check_modules.py says whether the modules still pass, and the copy, ORIGIN and any module
# change it needs are committed together.
set -euo pipefail
REPO=OpenSpineConsortium/hpcworker
EXPORT=module-schema WANT=1   # the export, and the version of it tools/check_modules.py reads
NEEDS=module-schema.json      # the file tools/check_modules.py reads from the copy
usage() { echo "usage: $0 [--ref REF]" >&2; exit 2; }
REF=main
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) [ $# -ge 2 ] || usage; REF="$2"; shift 2 ;;
    --from|--from=*) echo "$0: there is no --from: the schema is taken from what hpcworker publishes on GitHub, never from a checkout of it" >&2; exit 2 ;;
    *) usage ;;
  esac
done
# a branch, tag or commit; never an option, a range or a path that climbs
[[ "$REF" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]*$ && "$REF" != *..* ]] || { echo "$0: --ref takes a branch, tag or commit (got '$REF')" >&2; exit 2; }
DEST="$(cd "$(dirname "$0")/../schema" && pwd)"
PY=python3
"$PY" -c '' 2>/dev/null || PY=python   # on Windows python3 can be the Store's stub
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 6))' 2>/dev/null || { echo "FAILED: python 3.6 or later is needed to read the export's manifest" >&2; exit 1; }
command -v gh >/dev/null || { echo "FAILED: gh is not installed; the schema is taken through gh and your own sign-in" >&2; exit 1; }

sha=$(gh api "repos/$REPO/commits/$REF" --jq .sha) || sha=
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "FAILED: $REPO has no commit for $REF" >&2; exit 1; }
default=$(gh api "repos/$REPO" --jq .default_branch) || { echo "FAILED: could not read $REPO's default branch" >&2; exit 1; }
status=$(gh api "repos/$REPO/compare/$default...$sha" --jq .status) || status=
case "$status" in
  identical|behind) ;;
  *) echo "FAILED: $sha is not on $REPO's $default (${status:-no answer}); take only what was merged there" >&2; exit 1 ;;
esac
fetch() { gh api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/$1?ref=$sha"; }

# the export's paths, as the provider's manifest at that commit lists them
manifest=$(fetch interface/INTERFACE.json) \
  || { echo "FAILED: $REPO has no interface/INTERFACE.json at $sha, so it offers no export $EXPORT to take yet; schema/ is unchanged" >&2; exit 1; }
patterns=$(printf '%s' "$manifest" | "$PY" -I -c '
import json, sys
m = json.load(sys.stdin)
e = [x for x in m.get("exports", []) if isinstance(x, dict) and x.get("id") == sys.argv[1]]
if not e or e[0].get("version") != int(sys.argv[2]):
    sys.exit("export %s version %s is not offered (offered: %s)" % (sys.argv[1], sys.argv[2], ", ".join(
        "%s %s" % (x.get("id"), x.get("version")) for x in m.get("exports", []) if isinstance(x, dict)) or "none"))
paths = e[0].get("paths")
if not (isinstance(paths, list) and paths and all(isinstance(p, str) and p and "\n" not in p and not p.startswith("/")
                                                  and ".." not in p.split("/") for p in paths)):
    sys.exit("export %s lists no usable paths: %r" % (sys.argv[1], paths))
print("\n".join(paths))' "$EXPORT" "$WANT") || { echo "FAILED: $REPO at $sha does not offer $EXPORT version $WANT; schema/ is unchanged" >&2; exit 1; }

# every file of the tree at that commit the export's paths cover ("dir/" a folder, "*" within one part
# of a path), as "<path> TAB <where it lands below schema/>": below the folder all the paths share
pats=()
while IFS= read -r p; do pats+=("$p"); done <<<"$patterns"
plan=$(gh api "repos/$REPO/git/trees/$sha?recursive=1" --jq 'if .truncated then "TRUNCATED" else (.tree[] | select(.type == "blob") | .path) end' \
  | "$PY" -I -c '
import re, sys
needs, pats = sys.argv[1], sys.argv[2:]
tree = [line for line in sys.stdin.read().split("\n") if line]
if "TRUNCATED" in tree:
    sys.exit("the tree listing came back truncated")

def covers(p, rel):
    if p.endswith("/"):
        return rel.startswith(p)
    return re.match("".join("[^/]*" if c == "*" else re.escape(c) for c in p) + r"\Z", rel) is not None

def folder(p):
    out = []
    for part in p.split("/")[:-1]:
        if "*" in part:
            break
        out.append(part)
    return out

base = folder(pats[0])
for p in pats[1:]:
    f = folder(p)
    n = 0
    while n < min(len(base), len(f)) and base[n] == f[n]:
        n += 1
    base = base[:n]
base = "/".join(base) + "/" if base else ""
files = sorted(rel for rel in tree if any(covers(p, rel) for p in pats))
lands = [rel[len(base):] for rel in files]
bad = [d for d in lands if d in ("ORIGIN", "README.md", "pull.sh") or "\t" in d]
if not files:
    sys.exit("the export covers no file at this commit")
if bad:
    sys.exit("the export would put %s in schema/, where the folder keeps its own" % ", ".join(bad))
if needs not in lands:
    sys.exit("the export holds no %s, the file tools/check_modules.py reads" % needs)
print("\n".join("%s\t%s" % pair for pair in zip(files, lands)))' "$NEEDS" "${pats[@]}") \
  || { echo "FAILED: could not tell which files the export $EXPORT holds at $sha; schema/ is unchanged" >&2; exit 1; }

# fetch every file before any is replaced, so a failure leaves the copy as it was
parts=()
cleanup() { [ "${#parts[@]}" -eq 0 ] || rm -f "${parts[@]}"; }
trap cleanup EXIT
while IFS=$'\t' read -r src rel; do
  mkdir -p "$(dirname "$DEST/$rel")"
  parts+=("$DEST/$rel.part")
  fetch "$src" >"$DEST/$rel.part" || { echo "FAILED: could not read $src at $sha; schema/ is unchanged" >&2; exit 1; }
  case "$rel" in
    *.json) "$PY" -I -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$DEST/$rel.part" 2>/dev/null \
              || { echo "FAILED: $src at $sha is not JSON; schema/ is unchanged" >&2; exit 1; } ;;
  esac
done <<<"$plan"
origin=("repository $REPO" "commit $sha" "export $EXPORT $WANT")
while IFS=$'\t' read -r src rel; do
  mv -f "$DEST/$rel.part" "$DEST/$rel"
  origin+=("sha256 $("$PY" -I -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$DEST/$rel") $rel")
done <<<"$plan"
parts=("$DEST/ORIGIN.part")
printf '%s\n' "${origin[@]}" >"$DEST/ORIGIN.part"
mv -f "$DEST/ORIGIN.part" "$DEST/ORIGIN"
parts=()
echo "schema/: $(printf '%s\n' "$plan" | wc -l | tr -d ' ') file(s) of $REPO's export $EXPORT $WANT at $sha"
while IFS= read -r f; do
  rel="${f#"$DEST"/}"
  case "$rel" in ORIGIN|README.md|pull.sh|*.part) continue ;; esac
  printf '%s\n' "$plan" | cut -f2 | grep -xF "$rel" >/dev/null && continue
  echo "not in the export any more: schema/$rel (remove it in a reviewed commit)"
done < <(find "$DEST" -type f | sort)
echo "now run python3 tools/check_modules.py and the tests, and commit schema/ with any module change they need"

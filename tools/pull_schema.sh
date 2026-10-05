#!/bin/bash
# Refresh schema/module-schema.json from hpcworker, the schema's home, and write schema/ORIGIN: the
# hpcworker commit it was made at and the file's sha256 (tests/test_check_modules.py checks the file
# against it). hpcworker prints the schema itself (`profile.py module-schema`); nothing of hpcworker
# is copied here but that output.
#
#   bash tools/pull_schema.sh --from DIR     DIR: an hpcworker checkout, its committed HEAD
#
# Only from a checkout: the schema is made by running hpcworker's own profile.py, and this script
# runs no code it fetched. The checkout must hold no uncommitted change to that file, so ORIGIN names
# what made the schema.
set -euo pipefail
REPO=OpenSpineConsortium/hpcworker
case "${1:-}" in
  --from) FROM="${2:?--from needs a directory}" ;;
  *) echo "usage: $0 --from HPCWORKER_DIR" >&2; exit 2 ;;
esac
cd "$(dirname "$0")/../schema"
[ -f "$FROM/framework/lib/profile.py" ] || { echo "FAILED: $FROM is not an hpcworker checkout" >&2; exit 1; }
[ -z "$(git -C "$FROM" status --porcelain -- framework/lib/profile.py)" ] \
  || { echo "FAILED: $FROM has an uncommitted change to framework/lib/profile.py" >&2; exit 1; }
sha=$(git -C "$FROM" rev-parse HEAD)
python3 "$FROM/framework/lib/profile.py" module-schema >module-schema.json.part \
  || { rm -f module-schema.json.part; echo "FAILED: profile.py module-schema" >&2; exit 1; }
python3 -m json.tool module-schema.json.part >/dev/null || { rm -f module-schema.json.part; echo "FAILED: not JSON" >&2; exit 1; }
mv -f module-schema.json.part module-schema.json
printf '%s\n' "repository $REPO" "commit $sha" "command python3 framework/lib/profile.py module-schema" \
  "sha256 $(sha256sum module-schema.json | cut -d' ' -f1) module-schema.json" >ORIGIN.part
mv -f ORIGIN.part ORIGIN
echo "schema/module-schema.json: $REPO at $sha"

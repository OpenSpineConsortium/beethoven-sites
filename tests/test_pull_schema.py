"""tools/pull_schema.sh against a stand-in for gh: it takes hpcworker's export module-schema version 1
only from a commit hpcworker's default branch contains, only the files the manifest at that commit
lists, writes ORIGIN in the standard's form, refuses in plain words while hpcworker publishes no
manifest (as on its main today), and never deletes. No network and no sign-in: the stand-in answers
the five calls the script makes from files in a temporary folder, so what is tested is the script's
own logic, not GitHub's answers or the jq filters gh applies. Python 3.6 standard library and bash."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = "OpenSpineConsortium/hpcworker"
MAIN = "1" * 40
BRANCH = "2" * 40

# the stand-in: every call is recorded in calls, and answered from repo.json and tree/<commit>/
FAKE_GH = r'''
import json, os, sys
home = os.environ["FAKE_GH"]
with open(os.path.join(home, "calls"), "a") as fh:
    fh.write(" ".join(sys.argv[1:]) + "\n")
with open(os.path.join(home, "repo.json")) as fh:
    repo = json.load(fh)
args, endpoint, i = sys.argv[1:], None, 1
if args[:1] != ["api"]:
    sys.exit("stand-in gh: only api")
while i < len(args):
    if args[i] in ("-H", "--jq"):
        i += 2
    else:
        endpoint, i = args[i], i + 1
name = "repos/" + repo["name"]

def missing():
    sys.stderr.write("gh: Not Found (HTTP 404)\n")
    sys.exit(1)

if endpoint == name:
    print(repo["default"])
elif endpoint.startswith(name + "/commits/"):
    sha = repo["refs"].get(endpoint[len(name + "/commits/"):]) or missing()
    print(sha)
elif endpoint.startswith(name + "/compare/" + repo["default"] + "..."):
    print(repo["status"][endpoint.rsplit("...", 1)[1]])
elif endpoint.startswith(name + "/contents/"):
    path, _, ref = endpoint[len(name + "/contents/"):].partition("?ref=")
    f = os.path.join(home, "tree", ref, path)
    os.path.isfile(f) or missing()
    with open(f, "rb") as fh:
        sys.stdout.buffer.write(fh.read())
elif endpoint.startswith(name + "/git/trees/") and endpoint.endswith("?recursive=1"):
    top = os.path.join(home, "tree", endpoint[len(name + "/git/trees/"):-len("?recursive=1")])
    os.path.isdir(top) or missing()
    for d, _dirs, names in sorted(os.walk(top)):
        for n in sorted(names):
            print(os.path.relpath(os.path.join(d, n), top).replace(os.sep, "/"))
else:
    missing()
'''


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class PullSchema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.root, self.gh, self.bin = os.path.join(t, "sites"), os.path.join(t, "gh"), os.path.join(t, "bin")
        os.makedirs(os.path.join(self.root, "tools"))
        shutil.copy(os.path.join(ROOT, "tools", "pull_schema.sh"), os.path.join(self.root, "tools"))
        shutil.copytree(os.path.join(ROOT, "schema"), os.path.join(self.root, "schema"))
        self.schema = os.path.join(self.root, "schema")
        os.makedirs(self.bin)
        with open(os.path.join(t, "fakegh.py"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(FAKE_GH)
        with open(os.path.join(self.bin, "gh"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write('#!/bin/bash\nexec "%s" "%s" "$@"\n' % (sys.executable.replace(os.sep, "/"),
                                                         os.path.join(t, "fakegh.py").replace(os.sep, "/")))
        os.chmod(os.path.join(self.bin, "gh"), 0o755)
        os.makedirs(self.gh)
        self.repo({"identical": MAIN, "ahead": BRANCH})
        # hpcworker's main as its pull request will leave it: the manifest, the schema and other files
        self.schema_bytes = b'{"schema_version": 1, "fields": {}}\n'
        self.provide(MAIN, "interface/sites/module-schema.json", self.schema_bytes)
        self.provide(MAIN, "framework/VERSION", b"17\n")
        self.manifest(MAIN, [{"id": "contract", "version": 1, "paths": ["interface/contract/"]},
                             {"id": "module-schema", "version": 1, "paths": ["interface/sites/module-schema.json"]}])
        self.before = self.snapshot()

    def tearDown(self):
        self.tmp.cleanup()

    def repo(self, commits):
        refs = dict((sha, sha) for sha in commits.values())
        refs["main"] = MAIN
        with open(os.path.join(self.gh, "repo.json"), "w") as fh:
            json.dump({"name": REPO, "default": "main", "refs": refs,
                       "status": dict((sha, status) for status, sha in commits.items())}, fh)

    def provide(self, commit, path, data):
        dest = os.path.join(self.gh, "tree", commit, path)
        if not os.path.isdir(os.path.dirname(dest)):
            os.makedirs(os.path.dirname(dest))
        with open(dest, "wb") as fh:
            fh.write(data)

    def manifest(self, commit, exports):
        self.provide(commit, "interface/INTERFACE.json", json.dumps(
            {"format": 1, "name": "hpcworker", "repository": REPO, "exports": exports, "imports": []}, indent=1).encode("utf-8"))

    def snapshot(self):
        out = {}
        for d, _dirs, names in os.walk(self.schema):
            for n in names:
                out[os.path.relpath(os.path.join(d, n), self.schema).replace(os.sep, "/")] = sha256(os.path.join(d, n))
        return out

    def run_pull(self, *args):
        env = dict(os.environ, FAKE_GH=self.gh, PATH=self.bin + os.pathsep + os.environ.get("PATH", ""))
        p = subprocess.run(["bash", os.path.join(self.root, "tools", "pull_schema.sh")] + list(args), env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
        return p.returncode, p.stdout + p.stderr

    def calls(self):
        try:
            with open(os.path.join(self.gh, "calls")) as fh:
                return fh.read().splitlines()
        except (IOError, OSError):
            return []

    def refused(self, code, words, *args):
        rc, out = self.run_pull(*args)
        self.assertEqual(rc, code, out)
        self.assertIn(words, out)
        self.assertEqual(self.snapshot(), self.before, "a refused pull changed schema/")
        return out

    def test_only_a_branch_tag_or_commit_and_never_a_checkout(self):
        self.refused(2, "never from a checkout", "--from", "DIR")
        self.refused(2, "usage:", "--ref")
        self.refused(2, "usage:", "main")
        for ref in ("../x", "-x", "main..other", "a b"):
            self.refused(2, "--ref takes a branch, tag or commit", "--ref", ref)
        self.assertEqual(self.calls(), [], "an argument refused after gh was asked")

    def test_refused_while_hpcworker_publishes_no_manifest(self):
        os.remove(os.path.join(self.gh, "tree", MAIN, "interface", "INTERFACE.json"))
        self.refused(1, "%s has no interface/INTERFACE.json at %s, so it offers no export module-schema to take yet; "
                        "schema/ is unchanged" % (REPO, MAIN))

    def test_only_what_the_default_branch_contains(self):
        self.provide(BRANCH, "interface/sites/module-schema.json", self.schema_bytes)
        self.manifest(BRANCH, [{"id": "module-schema", "version": 1, "paths": ["interface/sites/module-schema.json"]}])
        self.refused(1, "%s is not on %s's main (ahead); take only what was merged there" % (BRANCH, REPO), "--ref", BRANCH)
        self.assertFalse([c for c in self.calls() if "/contents/" in c], "read a file of a commit main does not contain")

    def test_only_the_version_this_checker_reads(self):
        self.manifest(MAIN, [{"id": "module-schema", "version": 2, "paths": ["interface/sites/module-schema.json"]}])
        out = self.refused(1, "does not offer module-schema version 1", "--ref", "main")
        self.assertIn("offered: module-schema 2", out)

    def test_an_export_without_the_file_the_checker_reads(self):
        self.provide(MAIN, "interface/sites/rules.json", b"{}\n")
        self.manifest(MAIN, [{"id": "module-schema", "version": 1, "paths": ["interface/sites/rules.json"]}])
        self.refused(1, "the export holds no module-schema.json, the file tools/check_modules.py reads")

    def test_a_file_that_is_not_json_changes_nothing(self):
        self.provide(MAIN, "interface/sites/module-schema.json", b"{ not json\n")
        self.refused(1, "interface/sites/module-schema.json at %s is not JSON; schema/ is unchanged" % MAIN)
        self.assertFalse([f for f in os.listdir(self.schema) if f.endswith(".part")])

    def test_the_copy_and_its_origin(self):
        with open(os.path.join(self.schema, "old.json"), "w") as fh:
            fh.write("{}\n")
        rc, out = self.run_pull()
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.schema, "module-schema.json"), "rb") as fh:
            self.assertEqual(fh.read(), self.schema_bytes)
        with open(os.path.join(self.schema, "ORIGIN"), encoding="utf-8", newline="") as fh:
            self.assertEqual(fh.read(), "repository %s\ncommit %s\nexport module-schema 1\nsha256 %s module-schema.json\n"
                             % (REPO, MAIN, hashlib.sha256(self.schema_bytes).hexdigest()))
        # never deletes: a file the export no longer holds is named for a person to remove
        self.assertTrue(os.path.isfile(os.path.join(self.schema, "old.json")))
        self.assertIn("not in the export any more: schema/old.json (remove it in a reviewed commit)", out)
        self.assertEqual(sorted(os.listdir(self.schema)), ["ORIGIN", "module-schema.json", "old.json"])
        # every file is read at the one commit the ref named, never at the moving branch
        reads = [c for c in self.calls() if "/contents/" in c]
        self.assertEqual([c.rsplit("?ref=", 1)[1] for c in reads], [MAIN, MAIN])
        self.assertIn("contents/interface/sites/module-schema.json?ref=" + MAIN, reads[-1])

    def test_a_folder_export_lands_below_the_folder_its_paths_share(self):
        self.provide(MAIN, "interface/sites/module-schema.json", self.schema_bytes)
        self.provide(MAIN, "interface/sites/more/notes.json", b"[]\n")
        self.manifest(MAIN, [{"id": "module-schema", "version": 1, "paths": ["interface/sites/"]}])
        rc, out = self.run_pull()
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.schema, "ORIGIN"), encoding="utf-8") as fh:
            self.assertEqual([line.split(" ")[2] for line in fh.read().splitlines() if line.startswith("sha256 ")],
                             ["module-schema.json", "more/notes.json"])
        self.assertTrue(os.path.isfile(os.path.join(self.schema, "more", "notes.json")))


if __name__ == "__main__":
    unittest.main()

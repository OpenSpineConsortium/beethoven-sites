"""The interface standard's rules 1 to 3 for this repository (interface/README.md): nothing here reads,
runs or copies a file of another Beethoven repository's checkout; what it offers is declared in
interface/INTERFACE.json, and every path declared there names a file; and what it takes from another
is a folder of exactly the files its ORIGIN lists, byte for byte, taken only by tools/pull_schema.sh.
A line that reaches a sibling checkout fails unless it is on the known list below with its reason, and
an entry that no longer matches fails too, so the list only shrinks. Python 3.6 standard library, and
no git needed (the CI's Python 3.6 container has none)."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SELF = "beethoven-sites"
STANDARD = "https://github.com/OpenSpineConsortium/beethoven/blob/main/INTERFACES.md"
# every other repository of the ecosystem and the names their checkouts had (the Desktop folders ashley
# and ashley-bridge), and the website's
OTHERS = ("beethoven", "hpcworker", "beethoven-extension", "beethoven-desktop", "beethoven-qa", "beethoven-agents",
          "beethoven-research", "beethoven-base", "beethoven-vscode", "ashley", "ashley-bridge",
          "openspineconsortium.github.io", "spinesurg-ct-nnunet", "u251-xenograft-rat-rnaseq-study")
_names = "|".join(re.escape(n) for n in sorted(OTHERS, key=len, reverse=True))
# a path made from this checkout's parent: "../<repo>", or "$(dirname ...)/<repo>" and the like
SIBLING_PATH = re.compile(r"(?:\.\./|\)/|\}/)(%s)(?![A-Za-z0-9_.-])" % _names)
# a variable whose value is another repository's checkout
CHECKOUT_VAR = re.compile(r"\b((?:HPCWORKER|ASHLEY|SITES|QA|BEETHOVEN_(?:SERVICE|QA|AGENTS|RESEARCH|SITES|EXTENSION|DESKTOP|VSCODE|BASE|HUB))_DIR)\b")
# a clone of another repository of the organisation, or a dependency on one by git address
CLONE = re.compile(r"\b(?:git clone|gh repo clone)\b[^\n]*?OpenSpineConsortium/(%s)\b" % _names, re.I)
GIT_DEPENDENCY = re.compile(r"(?:git\+\w+://|github:)[^\s\"']*OpenSpineConsortium/(%s)\b" % _names, re.I)
CHECKOUT_ACTION_REPO = re.compile(r"^\s*repository:\s*\S+", re.M)
# the export kinds the standard defines
KINDS = {"contract", "schema", "data", "python", "cli", "files", "program", "text"}
# besides the export's files, an import's folder may hold only these
OWN = {"ORIGIN", "README.md", "pull.sh"}

# (file, what matched) -> why it is still here and who removes it
KNOWN = {}


def tracked():
    """the repository's files: git's list where git is at hand, else the tree without .git and caches"""
    try:
        out = subprocess.run(["git", "-C", REPO, "ls-files", "-z"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        files = [f for f in out.decode("utf-8").split("\0") if f]
        if files:
            return files
    except (OSError, subprocess.CalledProcessError):
        pass
    found = []
    for d, dirs, names in os.walk(REPO):
        dirs[:] = [x for x in dirs if x not in (".git", "__pycache__")]
        found += [os.path.relpath(os.path.join(d, n), REPO).replace(os.sep, "/") for n in names if not n.endswith(".pyc")]
    return sorted(found)


def text(rel):
    try:
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            return fh.read()
    except (UnicodeDecodeError, OSError):
        return ""


def manifest():
    with open(os.path.join(REPO, "interface", "INTERFACE.json"), encoding="utf-8") as fh:
        return json.load(fh)


def covered(rel, path):
    """the standard's path rule: "dir/" every file under it, "*" within one part of a path"""
    if path.endswith("/"):
        return rel.startswith(path)
    return re.match("".join("[^/]*" if c == "*" else re.escape(c) for c in path) + r"\Z", rel) is not None


def origin_record(path):
    """(repository, commit, [export lines], {file: sha256}) from an ORIGIN, which holds the standard's
    lines in its order and nothing else: repository, commit, at most one export, one sha256 per file"""
    with open(path, encoding="utf-8", newline="") as fh:
        body = fh.read()
    if not body.endswith("\n") or "\r" in body:
        raise ValueError("%s: lines end in one LF each" % path)
    lines = body[:-1].split("\n")
    if len(lines) < 3 or not re.match(r"repository OpenSpineConsortium/[a-z0-9.-]+\Z", lines[0]) \
            or not re.match(r"commit [0-9a-f]{40}\Z", lines[1]):
        raise ValueError("%s: begins with a repository line and a commit line" % path)
    rest = lines[2:]
    exports = [rest.pop(0)] if rest[0].startswith("export ") else []
    if exports and not re.match(r"export [a-z0-9][a-z0-9-]* [1-9][0-9]*\Z", exports[0]):
        raise ValueError("%s: an export line names an export and its version: %r" % (path, exports[0]))
    files = {}
    for line in rest:
        m = re.match(r"sha256 ([0-9a-f]{64}) (\S+)\Z", line)
        if not m or m.group(2) in files:
            raise ValueError("%s: after the commit and export lines come only sha256 lines, one per file: %r" % (path, line))
        files[m.group(2)] = m.group(1)
    if not files:
        raise ValueError("%s: lists no file" % path)
    return lines[0].split(" ", 1)[1], lines[1].split(" ", 1)[1], [e.split(" ")[1:] for e in exports], files


class SealedTree(unittest.TestCase):
    """Rule 1: the repository builds, tests and runs from its own tree."""

    def test_nothing_reaches_a_sibling_checkout(self):
        found = {}
        for rel in tracked():
            if rel.endswith(".md") or rel == "tests/test_boundary.py":
                continue   # prose may name another repository; this file names them to look for them
            for n, line in enumerate(text(rel).split("\n"), 1):
                for rx in (SIBLING_PATH, CHECKOUT_VAR, CLONE, GIT_DEPENDENCY):
                    for m in rx.finditer(line):
                        found.setdefault((rel, m.group(1)), "%s:%d: %s" % (rel, n, line.strip()[:160]))
        new = dict((k, v) for k, v in found.items() if k not in KNOWN)
        self.assertEqual(new, {}, "these lines reach another repository's checkout; take what is needed from that "
                                  "repository's interface instead (interface/README.md)")
        stale = sorted(k for k in KNOWN if k not in found)
        self.assertEqual(stale, [], "fixed: remove these from KNOWN in tests/test_boundary.py")

    def test_the_patterns_find_what_they_look_for(self):
        """the checks above are only as good as their patterns: each finds the line it exists for"""
        for line, rx in (('bash tools/pull_schema.sh --from ../hpcworker', SIBLING_PATH),
                         ('FROM="$(dirname "$HERE")/hpcworker"', SIBLING_PATH),
                         ('python3 "${ROOT}/beethoven-qa/x.py"', SIBLING_PATH),
                         ('echo "usage: $0 --from HPCWORKER_DIR"', CHECKOUT_VAR),
                         ('git clone https://github.com/OpenSpineConsortium/hpcworker', CLONE),
                         ('"dep": "git+https://github.com/OpenSpineConsortium/beethoven-qa.git"', GIT_DEPENDENCY)):
            with self.subTest(line=line):
                self.assertTrue(rx.search(line), line)
        for line in ('"site": "../x"', "repository OpenSpineConsortium/hpcworker", "/rs/rs_grp_oschome/$USER/hpcworker",
                     "../beethoven-sites-old", "gh api repos/OpenSpineConsortium/hpcworker/commits/main"):
            with self.subTest(line=line):
                self.assertFalse([rx for rx in (SIBLING_PATH, CHECKOUT_VAR, CLONE, GIT_DEPENDENCY) if rx.search(line)], line)

    def test_no_submodule_and_no_other_repository_checked_out_in_ci(self):
        self.assertFalse(os.path.exists(os.path.join(REPO, ".gitmodules")))
        for rel in tracked():
            if rel.startswith(".github/workflows/"):
                self.assertIsNone(CHECKOUT_ACTION_REPO.search(text(rel)), "%s checks out another repository" % rel)


class Declared(unittest.TestCase):
    """Rule 2: interface/INTERFACE.json declares every export and every import, in the standard's form."""

    def test_shape(self):
        m = manifest()
        self.assertEqual(sorted(m), ["exports", "format", "imports", "name", "repository", "standard", "summary"])
        self.assertEqual((m["format"], m["name"], m["repository"], m["standard"]),
                         (1, SELF, "OpenSpineConsortium/" + SELF, STANDARD))
        self.assertTrue(isinstance(m["summary"], str) and m["summary"])
        ids = [e["id"] for e in m["exports"]]
        self.assertEqual(len(ids), len(set(ids)), ids)
        for e in m["exports"]:
            with self.subTest(export=e["id"]):
                self.assertEqual(sorted(e), ["consumers", "id", "kind", "paths", "summary", "version"])
                self.assertRegex(e["id"], r"^[a-z0-9][a-z0-9-]*$")
                self.assertIn(e["kind"], KINDS)
                self.assertTrue(isinstance(e["version"], int) and not isinstance(e["version"], bool) and e["version"] >= 1)
                self.assertTrue(isinstance(e["paths"], list) and e["paths"])
                for p in e["paths"]:
                    self.assertTrue(isinstance(p, str) and p and not p.startswith("/") and ".." not in p.split("/"), p)
                for c in e["consumers"]:
                    self.assertRegex(c, r"^OpenSpineConsortium/[a-z0-9.-]+$")
        intos = [i["into"] for i in m["imports"]]
        self.assertEqual(len(intos), len(set(intos)), intos)
        for i in m["imports"]:
            with self.subTest(into=i.get("into")):
                self.assertEqual(sorted(i), ["export", "into", "origin", "repository", "version"])
                self.assertRegex(i["repository"], r"^OpenSpineConsortium/[a-z0-9.-]+$")
                self.assertNotEqual(i["repository"], "OpenSpineConsortium/" + SELF)
                self.assertTrue(isinstance(i["version"], int) and not isinstance(i["version"], bool) and i["version"] >= 1)
                self.assertEqual(i["origin"], i["into"] + "/ORIGIN")

    def test_every_export_path_names_a_file(self):
        files = tracked()
        for e in manifest()["exports"]:
            for p in e["paths"]:
                with self.subTest(export=e["id"], path=p):
                    self.assertTrue([f for f in files if covered(f, p)], "%s names no file" % p)

    def test_the_modules_export_holds_every_module(self):
        """hpcworker's framework/sites/pull.sh takes the files the export "modules" lists; a module it
        does not list would pass here and never reach a profile"""
        export = [e for e in manifest()["exports"] if e["id"] == "modules"]
        self.assertEqual([(e["kind"], e["version"]) for e in export], [("data", 1)])
        modules = [f for f in tracked() if f.startswith("sites/") and f.endswith(".json")]
        self.assertTrue(modules)
        self.assertEqual([f for f in modules if not any(covered(f, p) for p in export[0]["paths"])], [])

    def test_the_path_rule(self):
        self.assertTrue(covered("sites/wayne/site.json", "sites/"))
        self.assertTrue(covered("framework/profiles/wayne.json", "framework/profiles/*.json"))
        self.assertFalse(covered("framework/profiles/old/wayne.json", "framework/profiles/*.json"))
        self.assertFalse(covered("framework/profilesXwayne.json", "framework/profiles/*.json"))
        self.assertTrue(covered("interface/sites/module-schema.json", "interface/sites/module-schema.json"))
        self.assertFalse(covered("interface/sites/module-schema.json.bak", "interface/sites/module-schema.json"))
        self.assertFalse(covered("sitesX/a.json", "sites/"))


class PinnedImports(unittest.TestCase):
    """Rule 3: each import is a folder of exactly the files its ORIGIN lists, byte for byte, taken only by
    its pull script from a merged commit of the provider."""

    def test_each_import_matches_its_origin(self):
        imports = manifest()["imports"]
        self.assertTrue(imports)
        for imp in imports:
            with self.subTest(into=imp["into"]):
                folder = os.path.join(REPO, imp["into"])
                repository, _commit, exports, recorded = origin_record(os.path.join(REPO, imp["origin"]))
                self.assertEqual(repository, imp["repository"])
                # a copy taken before its provider published INTERFACE.json has no export line; the next pull writes one
                for e in exports:
                    self.assertEqual(e, [imp["export"], str(imp["version"])])
                present = {}
                for d, dirs, names in os.walk(folder):
                    dirs[:] = [x for x in dirs if x != "__pycache__"]
                    for n in names:
                        rel = os.path.relpath(os.path.join(d, n), folder).replace(os.sep, "/")
                        if rel in OWN or n.endswith(".pyc"):
                            continue
                        with open(os.path.join(d, n), "rb") as fh:
                            present[rel] = hashlib.sha256(fh.read()).hexdigest()
                self.assertEqual(present, recorded, "%s differs from %s: take a new copy with its pull script, "
                                                    "never by hand" % (imp["into"], imp["origin"]))

    def test_the_pull_script_takes_what_the_import_names(self):
        """tools/pull_schema.sh asks hpcworker for the export and version the manifest's import names, and
        reads nothing but GitHub through gh"""
        imp = [i for i in manifest()["imports"] if i["into"] == "schema"]
        self.assertEqual(len(imp), 1)
        body = text("tools/pull_schema.sh")
        self.assertIn("REPO=%s\n" % imp[0]["repository"], body)
        self.assertRegex(body, r"\nEXPORT=%s WANT=%d\b" % (re.escape(imp[0]["export"]), imp[0]["version"]))
        self.assertIn('DEST="$(cd "$(dirname "$0")/../%s" && pwd)"' % imp[0]["into"], body)
        self.assertNotRegex(body, r"\bgit (?:-C|show|ls-tree|clone|fetch)\b")

    def test_an_origin_in_another_form_is_refused(self):
        good = ["repository OpenSpineConsortium/hpcworker", "commit " + "a" * 40, "export module-schema 1",
                "sha256 " + "b" * 64 + " module-schema.json"]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ORIGIN")

            def record(lines, end="\n"):
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(end.join(lines) + end)
                return origin_record(path)
            self.assertEqual(record(good), ("OpenSpineConsortium/hpcworker", "a" * 40, [["module-schema", "1"]],
                                            {"module-schema.json": "b" * 64}))
            self.assertEqual(record(good[:2] + good[3:])[2], [])
            for bad in (good[:2] + ["command python3 framework/lib/profile.py module-schema"] + good[3:],
                        good[1:2] + good[:1] + good[2:], good[:3], good + [good[3]], good[:2] + good[3:] + good[2:3],
                        good[:2] + ["export module-schema one"] + good[3:], ["repository hpcworker"] + good[1:]):
                with self.subTest(lines=bad):
                    with self.assertRaises(ValueError):
                        record(bad)
            with self.assertRaises(ValueError):
                record(good, end="\r\n")


if __name__ == "__main__":
    unittest.main()

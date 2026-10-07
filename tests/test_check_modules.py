"""tools/check_modules.py: every module in this repository passes, and each kind of mistake a module
can make on its own is refused with words that say what to change. The schema copy is checked
against its ORIGIN record. Python 3.6 standard library, like the checker."""
import copy
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
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_modules as C  # noqa: E402

SCHEMA = C.load_schema()


def modules():
    """[(site.json, lab.json)] for every lab in the repository"""
    out = []
    sites = os.path.join(ROOT, "sites")
    for name in sorted(os.listdir(sites)):
        labs = os.path.join(sites, name, "labs")
        for fn in sorted(os.listdir(labs)) if os.path.isdir(labs) else []:
            if fn.endswith(".json"):
                out.append((os.path.join(sites, name, "site.json"), os.path.join(labs, fn)))
    return out


class Repository(unittest.TestCase):
    def test_every_module_here_passes(self):
        problems, n_sites, n_labs = C.check_tree()
        self.assertEqual(problems, [])
        self.assertGreaterEqual(n_sites, 1)
        self.assertGreaterEqual(n_labs, 1)

    def test_the_command_line(self):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_modules.py")],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.decode("utf-8").startswith("ok: "))
        p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_modules.py"), "--root"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(p.returncode, 2)

    def test_the_schema_copy_is_what_its_origin_records(self):
        with open(os.path.join(ROOT, "schema", "ORIGIN"), encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        self.assertEqual(lines[0], "repository OpenSpineConsortium/hpcworker")
        self.assertRegex(lines[1], r"^commit [0-9a-f]{40}$")
        sha = [line.split(" ") for line in lines if line.startswith("sha256 ")]
        self.assertEqual([s[2] for s in sha], ["module-schema.json"])
        with open(os.path.join(ROOT, "schema", "module-schema.json"), "rb") as fh:
            self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), sha[0][1])

    def test_the_schema_is_whole(self):
        self.assertEqual(SCHEMA["layers"], ["product", "site", "lab"])
        for key, spec in SCHEMA["fields"].items():
            self.assertTrue(spec["layers"] and set(spec["layers"]) <= set(SCHEMA["layers"]), key)
            for typed in [spec] + spec.get("keys", []):
                C.type_ok(typed, None)  # every type is one the checker knows (raises otherwise)
        for key in SCHEMA["product"]:
            self.assertIn("product", SCHEMA["fields"][key]["layers"], key)
        self.assertTrue(C.id_ok("wayne", SCHEMA))

    def test_a_schema_this_checker_does_not_know_is_refused(self):
        with self.assertRaises(ValueError):
            C.type_ok({"type": "float"}, 1.0)
        with self.assertRaises(ValueError):
            C.id_ok("wayne", dict(SCHEMA, id_match="prefix"))

    def test_the_pinned_schema_is_one_this_checker_can_apply(self):
        self.assertEqual(C.schema_problems(SCHEMA), [])
        self.assertEqual(C.module_kinds(SCHEMA), ["site", "lab"])

    def test_what_the_checker_cannot_apply_is_found_before_any_module_is_read(self):
        """a type, an id match or a module kind this checker does not know fails the whole check, even
        where no module uses it, and names what to change"""
        schema = copy.deepcopy(SCHEMA)
        schema["fields"]["notes"]["type"] = "text"
        schema["fields"]["egress"]["keys"][1]["type"] = "map"
        schema["id_match"] = "prefix"
        schema["module_keys"]["group"] = ["kind"]
        problems = C.schema_problems(schema)
        self.assertEqual(len(problems), 4, problems)
        for words in ("module kinds are group/lab/site, but sites/ holds site/lab", "an id match this checker does not know: 'prefix'",
                      "field egress.proxy_env: the schema names a type this checker does not know: 'map'",
                      "field notes: the schema names a type this checker does not know: 'text'"):
            self.assertTrue([p for p in problems if words in p and p.endswith(C.NEW_TO_CHECKER)], (words, problems))
        found, n_sites, n_labs = C.check_tree(schema=schema)
        self.assertEqual((found, n_sites, n_labs), (["schema/module-schema.json: " + p for p in problems], 0, 0))

    def test_which_layers_are_modules_comes_from_the_schema(self):
        """a layer the schema's module_keys does not name is no module's, whatever it is called"""
        schema = copy.deepcopy(SCHEMA)
        schema["fields"]["display_name"]["layers"] = ["product"]
        self.assertEqual(C.owner("display_name", "lab", schema), "display_name is the product's own value; no module sets it")
        schema["fields"]["display_name"]["layers"] = ["account", "site"]
        self.assertEqual(C.owner("display_name", "lab", schema), "display_name is set by the site module, not by a lab module")


class Module(unittest.TestCase):
    def setUp(self):
        site_path, lab_path = modules()[0]
        self.site, self.lab = C.read_json(site_path), C.read_json(lab_path)

    def refused(self, mod, kind, words):
        errs = C.check_module(mod, kind, SCHEMA)
        self.assertTrue(any(words in e for e in errs), (words, errs))

    def test_the_modules_pass_alone(self):
        self.assertEqual(C.check_module(self.site, "site", SCHEMA), [])
        self.assertEqual(C.check_module(self.lab, "lab", SCHEMA), [])

    def test_an_unknown_key_is_a_typo(self):
        self.site["submit_hots"] = "x"
        self.refused(self.site, "site", "submit_hots is not a field of the profile")

    def test_a_key_inside_an_object_field_is_checked_too(self):
        site = copy.deepcopy(self.site)
        site["login_node_rules"] = {"max_proceses": 10}
        self.refused(site, "site", "login_node_rules.max_proceses is not a key of login_node_rules "
                                   "(it has max_processes, poll_floor_seconds)")
        lab = copy.deepcopy(self.lab)
        lab["worker_defaults"] = {"hours": "12"}
        self.refused(lab, "lab", "field worker_defaults.hours: expected int, got '12'")
        lab["image_store"] = {"type": "squashfs", "path": "/x"}
        self.refused(lab, "lab", "field image_store.type: expected sandbox/sif")

    def test_each_layer_sets_only_its_own(self):
        lab = copy.deepcopy(self.lab)
        lab["ssh_host_key"] = "SHA256:" + "A" * 43
        self.refused(lab, "lab", "ssh_host_key is set by the site module, not by a lab module")
        site = copy.deepcopy(self.site)
        site["shared_state_dir"] = "/x/$USER"
        self.refused(site, "site", "shared_state_dir is set by the lab module, not by a site module")
        for mod, kind in ((copy.deepcopy(self.site), "site"), (copy.deepcopy(self.lab), "lab")):
            mod["claude_config_dir"] = "$HOME/.claude"
            self.refused(mod, kind, "claude_config_dir is the product's own value; no module sets it")

    def test_a_field_the_product_shares_names_the_module_that_may_set_it(self):
        site = copy.deepcopy(self.site)
        site["login_abandon_s"] = 600
        self.refused(site, "site", "login_abandon_s is set by the lab module, not by a site module")
        lab = copy.deepcopy(self.lab)
        lab["login_node_rules"] = {"max_processes": 10}
        self.refused(lab, "lab", "login_node_rules is set by the site module, not by a lab module")

    def test_a_credential_shape_the_schema_refuses_is_refused_anywhere_in_a_module(self):
        # the pinned schema carries hpcworker's rule (refused_values, from its interface on), so a module
        # with a credential's shape fails here, before it merges, and not only when hpcworker composes it
        schema = SCHEMA
        self.assertEqual([r["why"] for r in schema["refused_values"]],
                         ["a profile is a settings file and never carries a credential"])
        self.assertEqual(C.check_module(self.site, "site", schema), [])
        self.site["notes"] = "paste sk-ant-abc here"
        self.lab["binds"] = ["/x/$USER", "CLAUDE_CODE_OAUTH_TOKEN=abc"]
        self.assertEqual(C.check_module(self.site, "site", schema),
                         ["field notes holds what no module may (a profile is a settings file and never carries a credential)"])
        self.assertTrue(any(e.startswith("field binds.1 holds what no module may") for e in C.check_module(self.lab, "lab", schema)))

    def test_a_wrong_type(self):
        self.lab["binds"] = "/x/$USER"
        self.refused(self.lab, "lab", "field binds: expected list")
        self.site["scheduler"] = "cron"
        self.refused(self.site, "site", "field scheduler: expected slurm/")

    def test_what_a_module_says_about_itself(self):
        site = copy.deepcopy(self.site)
        site["kind"] = "lab"
        self.refused(site, "site", "kind must be 'site' in a site module")
        lab = copy.deepcopy(self.lab)
        lab["kind"] = "site"
        self.refused(lab, "lab", "kind must be 'lab' in a lab module")
        for mv in (0, "1", True, None):
            lab = copy.deepcopy(self.lab)
            lab["module_version"] = mv
            self.refused(lab, "lab", "module_version must be a whole number from 1")
        for key, bad in (("lab", "Two Words"), ("profile", ""), ("site", "../x"), ("lab", "x\n")):
            lab = copy.deepcopy(self.lab)
            lab[key] = bad
            self.refused(lab, "lab", "%s must be lower-case letters, digits and dashes" % key)
        self.refused([], "site", "the site module is not a JSON object")

    def test_a_labs_profile_carries_its_sites_id_until_accounts_name_theirs(self):
        lab = dict(self.lab, profile=self.lab["site"] + "-second")
        self.refused(lab, "lab", "profile must be %r, the site's id" % self.lab["site"])
        self.assertEqual(C.check_module(lab, "lab", dict(SCHEMA, profile_is_site=False)), [])


class Tree(unittest.TestCase):
    """the checker over a copy of sites/ and schema/"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for d in ("sites", "schema"):
            shutil.copytree(os.path.join(ROOT, d), os.path.join(self.root, d))
        site_path, lab_path = modules()[0]
        self.site_rel = os.path.relpath(site_path, ROOT).replace(os.sep, "/")
        self.lab_rel = os.path.relpath(lab_path, ROOT).replace(os.sep, "/")
        self.site = C.read_json(site_path)
        self.lab = C.read_json(lab_path)
        self.site_id = self.lab["site"]

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, obj):
        path = os.path.join(self.root, rel)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(obj if isinstance(obj, str) else json.dumps(obj, indent=1) + "\n")

    def problems(self):
        return C.check_tree(self.root)[0]

    def test_a_module_sits_where_its_ids_say(self):
        self.write("sites/%s/labs/misnamed.json" % self.site_id, self.lab)
        self.assertIn("sites/%s/labs/misnamed.json: its lab id must be 'misnamed' and its site %r, as the path says"
                      % (self.site_id, self.site_id), self.problems())

    def test_a_site_folder_is_named_by_its_id(self):
        self.write("sites/elsewhere/site.json", self.site)
        self.assertIn("sites/elsewhere/site.json: its site id must be 'elsewhere', the folder's name", self.problems())

    def test_a_site_folder_without_site_json(self):
        os.makedirs(os.path.join(self.root, "sites", "empty"))
        self.assertIn("sites/empty: no site.json", self.problems())

    def test_a_site_module_with_no_lab_yet_is_checked(self):
        self.write("sites/abc/site.json", dict(self.site, site="abc", submit_hots="x"))
        self.assertIn("sites/abc/site.json: submit_hots is not a field of the profile (schema/module-schema.json lists them)",
                      self.problems())

    def test_two_labs_may_not_name_one_profile(self):
        self.write("sites/%s/labs/second.json" % self.site_id, dict(self.lab, lab="second"))
        self.assertIn("%s and sites/%s/labs/second.json both compose profiles/%s.json" % (self.lab_rel, self.site_id, self.lab["profile"]),
                      self.problems())

    def test_the_profile_must_be_whole(self):
        lab = dict(self.lab)
        del lab["shared_state_dir"]
        self.write(self.lab_rel, lab)
        self.assertIn("%s: the profile it composes with %s lacks shared_state_dir, which neither sets" % (self.lab_rel, self.site_rel),
                      self.problems())

    def test_a_key_the_profile_must_hold_inside_an_object(self):
        """the product holds the poll floor; the login node's process cap is the site's to state"""
        self.write(self.site_rel, dict(self.site, login_node_rules={"poll_floor_seconds": 120}))
        self.assertIn("%s: the profile it composes with %s lacks login_node_rules.max_processes, which neither sets"
                      % (self.lab_rel, self.site_rel), self.problems())

    def test_a_file_that_is_not_json(self):
        self.write(self.lab_rel, "{ not json")
        problems = self.problems()
        self.assertEqual(len(problems), 1)
        self.assertIn("%s: could not be read as JSON" % self.lab_rel, problems[0])

    def test_other_files_beside_the_modules_are_left_alone(self):
        self.write("sites/%s/README.md" % self.site_id, "# notes\n")
        self.write("sites/%s/labs/README.md" % self.site_id, "# labs\n")
        self.assertEqual(self.problems(), [])

    def test_a_new_university_with_its_own_lab_passes(self):
        self.write("sites/example/site.json", dict(self.site, site="example", display_name="Example University"))
        self.write("sites/example/labs/lab1.json", dict(self.lab, site="example", lab="lab1", profile="example"))
        problems, _n_sites, n_labs = C.check_tree(self.root)
        self.assertEqual((problems, n_labs), ([], len(modules()) + 1))


if __name__ == "__main__":
    unittest.main()

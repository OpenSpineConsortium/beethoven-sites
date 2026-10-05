#!/usr/bin/env python3
"""Check every site and lab module under sites/ against the module schema hpcworker publishes
(schema/module-schema.json, pinned by schema/ORIGIN). Python 3.6 standard library only, nothing
imported from hpcworker, so whoever writes a module can check it with this repository alone.

    python3 tools/check_modules.py [--root DIR]

It checks what the modules show on their own: each file sits where its ids say, carries only the
schema's fields and, inside an object field, only the keys the schema names, sets only what its
layer may set (a lab never pins a host key, a site never names a lab's volume, no module moves the
student's sign-in), with the right types; a lab belongs to its site, no two labs name one profile,
and the product, the site and the lab together set every field and key a profile must have. The whole composed profile (a host key's form, a link being https, the poll
floor) is checked by hpcworker when it composes the modules it pins (`profile.py compose-all
--check` there); a module that passes here and fails there is a schema this copy does not yet have.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError) as e:
        raise ValueError("%s: could not be read as JSON (%s)" % (path, e))


def load_schema(root=None):
    return read_json(os.path.join(root or ROOT, "schema", "module-schema.json"))


def type_ok(spec, value):
    t = spec["type"]
    if t == "enum":
        return isinstance(value, str) and value in spec["values"]
    if t == "str":
        return isinstance(value, str)
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "bool":
        return isinstance(value, bool)
    if t == "list":
        return isinstance(value, list)
    if t == "dict":
        return isinstance(value, dict)
    if t == "int_or_none":
        return value is None or (isinstance(value, int) and not isinstance(value, bool))
    if t == "bool_or_none":
        return value is None or isinstance(value, bool)
    if t == "str_or_none":
        return value is None or isinstance(value, str)
    raise ValueError("the schema names a type this checker does not know: %r (pull a newer checker)" % t)


def describe(spec):
    return "/".join(spec["values"]) if spec["type"] == "enum" else spec["type"]


def id_ok(value, schema):
    """an id is matched whole, as hpcworker does (a "$" alone would let a trailing newline through)"""
    if schema.get("id_match") != "whole":
        raise ValueError("the schema asks for an id match this checker does not know: %r (pull a newer checker)" % schema.get("id_match"))
    return isinstance(value, str) and re.fullmatch(schema["id_pattern"], value) is not None


def owner(key, kind, schema):
    modules = [layer for layer in schema["fields"][key]["layers"] if layer != "product"]
    if not modules:
        return "%s is the product's own value; no module sets it" % key
    return "%s is set by the %s module, not by a %s module" % (key, " or the ".join(modules), kind)


def check_module(mod, kind, schema):
    """Problems with one module on its own; the same rules as hpcworker's validate_module."""
    if not isinstance(mod, dict):
        return ["the %s module is not a JSON object" % kind]
    errs = []
    if mod.get("kind") != kind:
        errs.append("kind must be %r in a %s module (got %r)" % (kind, kind, mod.get("kind")))
    mv = mod.get("module_version")
    if not (isinstance(mv, int) and not isinstance(mv, bool) and mv >= 1):
        errs.append("module_version must be a whole number from 1 (got %r)" % (mv,))
    for key in (("site",) if kind == "site" else ("site", "lab", "profile")):
        if not id_ok(mod.get(key), schema):
            errs.append("%s must be lower-case letters, digits and dashes (got %r)" % (key, mod.get(key)))
    if kind == "lab" and schema.get("profile_is_site") and mod.get("profile") != mod.get("site"):
        errs.append("profile must be %r, the site's id: the framework finds a deployment's profile by its site's id, "
                    "so a site has one lab until BEE-208 (got %r)" % (mod.get("site"), mod.get("profile")))
    fields = schema["fields"]
    for key, value in mod.items():
        if key in schema["module_keys"][kind]:
            continue
        if key not in fields:
            errs.append("%s is not a field of the profile (schema/module-schema.json lists them)" % key)
            continue
        if kind not in fields[key]["layers"]:
            errs.append(owner(key, kind, schema))
            continue
        if not type_ok(fields[key], value):
            errs.append("field %s: expected %s, got %r" % (key, describe(fields[key]), value))
            continue
        subs = dict((sub["name"], sub) for sub in fields[key].get("keys", []))
        for sub in value if "keys" in fields[key] else ():
            if sub not in subs:
                errs.append("%s.%s is not a key of %s (it has %s)" % (key, sub, key, ", ".join(s["name"] for s in fields[key]["keys"])))
            elif not type_ok(subs[sub], value[sub]):
                errs.append("field %s.%s: expected %s, got %r" % (key, sub, describe(subs[sub]), value[sub]))
    return errs


def missing(site, lab, schema):
    """the fields, and the keys inside an object field, a profile must carry that neither the product
    nor SITE nor LAB sets"""
    product, out = schema["product"], []
    for key, spec in schema["fields"].items():
        layers = [m[key] for m in (product, site, lab) if key in m]
        if spec.get("required") and not layers:
            out.append(key)
        for sub in spec.get("keys", []):
            if sub["required"] and layers and not any(isinstance(v, dict) and sub["name"] in v for v in layers):
                out.append("%s.%s" % (key, sub["name"]))
    return out


def check_tree(root=None, schema=None):
    """(problems, number of sites, number of labs) for every module under ROOT/sites."""
    root = root or ROOT
    schema = schema or load_schema(root)
    sites_dir = os.path.join(root, "sites")
    problems, n_sites, n_labs, profiles = [], 0, 0, {}

    def rel(path):
        return os.path.relpath(path, root).replace(os.sep, "/")

    for name in sorted(os.listdir(sites_dir)) if os.path.isdir(sites_dir) else []:
        folder = os.path.join(sites_dir, name)
        if not os.path.isdir(folder):
            continue
        site_path = os.path.join(folder, "site.json")
        if not os.path.isfile(site_path):
            problems.append("%s: no site.json" % rel(folder))
            continue
        try:
            site = read_json(site_path)
        except ValueError as e:
            problems.append(str(e).replace(site_path, rel(site_path)))
            continue
        n_sites += 1
        problems += ["%s: %s" % (rel(site_path), e) for e in check_module(site, "site", schema)]
        if isinstance(site, dict) and site.get("site") != name:
            problems.append("%s: its site id must be %r, the folder's name" % (rel(site_path), name))
        labs = os.path.join(folder, "labs")
        for fn in sorted(os.listdir(labs)) if os.path.isdir(labs) else []:
            lab_path = os.path.join(labs, fn)
            if not fn.endswith(".json"):
                continue
            try:
                lab = read_json(lab_path)
            except ValueError as e:
                problems.append(str(e).replace(lab_path, rel(lab_path)))
                continue
            n_labs += 1
            errs = check_module(lab, "lab", schema)
            problems += ["%s: %s" % (rel(lab_path), e) for e in errs]
            if not isinstance(lab, dict):
                continue
            if lab.get("lab") != fn[:-5] or lab.get("site") != name:
                problems.append("%s: its lab id must be %r and its site %r, as the path says" % (rel(lab_path), fn[:-5], name))
            pid = lab.get("profile")
            if isinstance(pid, str):
                if pid in profiles:
                    problems.append("%s and %s both compose profiles/%s.json" % (profiles[pid], rel(lab_path), pid))
                else:
                    profiles[pid] = rel(lab_path)
            if isinstance(site, dict):
                for key in missing(site, lab, schema):
                    problems.append("%s: the profile it composes with %s lacks %s, which neither sets"
                                    % (rel(lab_path), rel(site_path), key))
    return problems, n_sites, n_labs


def main(argv):
    args = argv[1:]
    root = None
    if args[:1] == ["--root"] and len(args) == 2:
        root = args[1]
    elif args:
        sys.stderr.write("usage: python3 tools/check_modules.py [--root DIR]\n")
        return 2
    try:
        problems, n_sites, n_labs = check_tree(root)
    except ValueError as e:
        problems, n_sites, n_labs = [str(e)], 0, 0
    for p in problems:
        print("ERROR: " + p)
    if not problems:
        print("ok: %d site module(s) and %d lab module(s) match schema/module-schema.json" % (n_sites, n_labs))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

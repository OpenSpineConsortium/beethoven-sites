#!/usr/bin/env python3
"""Check every site and lab module under sites/, and the synthetic ones under examples/, against the
module schema hpcworker publishes (schema/module-schema.json, its export module-schema, pinned by
schema/ORIGIN). Python 3.6 standard library only, nothing imported from hpcworker, so whoever writes a
module can check it with this repository alone.

    python3 tools/check_modules.py [--root DIR]

It checks what the modules show on their own: each file sits where its ids say, carries only the
schema's fields and, inside an object field, only the keys the schema names, sets only what its
layer may set (a lab never pins a host key, a site never names a lab's volume, no module moves the
student's sign-in), with the right types; a lab belongs to its site, no two labs name one profile,
and the product, the site and the lab together set every field and key a profile must have.

Each rule comes from the schema wherever the schema states it: the fields, their types and the layers
that may set them, the keys inside an object field, what a profile must carry, the product's values,
the keys a module says about itself, the id pattern, and whether a lab's profile is its site's. What
module-schema 1 does not state is written here, marked so, and listed in interface/README.md with
what the schema would need to carry. The schema's refused_values (a credential's shape, published by
hpcworker with its interface) are refused in every string of a module. The composed profile's other value rules (a host key's form, a link being https, the poll
floor's minimum) are in no schema yet, so only hpcworker applies them, when it composes the modules it pins (`profile.py compose-all --check`
there): a module that passes here and fails there breaks one of those.

A module under examples/ is a university that does not exist (the export example-modules, never the
export modules, so no profile of it reaches a student). It follows every rule above in the same layout,
shares no site or profile id with sites/, and must never name a real machine: each host and link sits
under a name reserved for examples (RFC 2606, RFC 6761), and nothing in it is a measurement (no host
key, nothing under egress.measured).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# The module kinds this repository's layout holds (sites/<site>/site.json, sites/<site>/labs/<lab>.json:
# the export "modules"); the schema's module_keys must name exactly these.
KINDS = ("site", "lab")
# Which keys of a module are ids, matched against the schema's id_pattern: a site module's "site" (the
# profile's field of that name) and a lab module's site, lab and profile. Not in module-schema 1.
IDS = {"site": ("site",), "lab": ("site", "lab", "profile")}


def _int(value):
    return isinstance(value, int) and not isinstance(value, bool)


# What each type name of the schema admits ("enum" admits a string among the field's values). The names
# are the schema's; what they admit is not in module-schema 1, so it is written here as hpcworker reads
# it: an integer is never a boolean, and "_or_none" also admits null.
TYPES = {
    "str": lambda v: isinstance(v, str),
    "int": _int,
    "bool": lambda v: isinstance(v, bool),
    "list": lambda v: isinstance(v, list),
    "dict": lambda v: isinstance(v, dict),
    "int_or_none": lambda v: v is None or _int(v),
    "bool_or_none": lambda v: v is None or isinstance(v, bool),
    "str_or_none": lambda v: v is None or isinstance(v, str),
}
# a schema that changes one of these comes with a change here, in the pull request that takes it
NEW_TO_CHECKER = "; tools/check_modules.py learns it in the pull request that takes this schema"

# The two trees of modules, in the layout of the export modules: the deployments, and the synthetic
# universities the tests of every consumer run beside them (the export example-modules).
SITES, EXAMPLES = "sites", "examples"
# Which fields of a module hold a host name, for the examples' rule. Not in module-schema 1 (it gives
# types, not formats); a link anywhere in a module is found by its scheme instead (LINK).
HOST_FIELDS = ("submit_host", "ood_shell_host", "vpn_portal", "ssh_host")
LINK = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://([^/\s:?#\"'\\]*)")
# the names no machine on the internet will ever answer to: RFC 2606's three second-level names and its
# top-level ones (with RFC 6761's .localhost)
RESERVED = re.compile(r"(?:^|\.)(?:example|test|invalid|localhost|example\.com|example\.net|example\.org)\Z", re.I)


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
    if t not in TYPES:
        raise ValueError("the schema names a type this checker does not know: %r%s" % (t, NEW_TO_CHECKER))
    return TYPES[t](value)


def describe(spec):
    return "/".join(spec["values"]) if spec["type"] == "enum" else spec["type"]


def id_ok(value, schema):
    """an id is matched whole, as hpcworker does (a "$" alone would let a trailing newline through)"""
    if schema.get("id_match") != "whole":
        raise ValueError("the schema asks for an id match this checker does not know: %r%s" % (schema.get("id_match"), NEW_TO_CHECKER))
    return isinstance(value, str) and re.fullmatch(schema["id_pattern"], value) is not None


def module_kinds(schema):
    """the layers a module may be, in the order they are laid down: those the schema's module_keys names
    (the others, the product, are the schema's own values)"""
    return [layer for layer in schema["layers"] if layer in schema["module_keys"]]


def schema_problems(schema):
    """What in SCHEMA this checker cannot apply: module kinds other than this repository's layout holds,
    an id match or a type name it does not know. Found before any module is read, so a schema that needs
    a newer checker says so even where no module uses what changed."""
    out = []
    if tuple(module_kinds(schema)) != KINDS or set(schema["module_keys"]) != set(KINDS):
        out.append("the schema's module kinds are %s, but sites/ holds %s%s"
                   % ("/".join(sorted(schema["module_keys"])), "/".join(KINDS), NEW_TO_CHECKER))
    if schema.get("id_match") != "whole":
        out.append("the schema asks for an id match this checker does not know: %r%s" % (schema.get("id_match"), NEW_TO_CHECKER))
    for key, spec in sorted(schema["fields"].items()):
        for typed in [spec] + spec.get("keys", []):
            if typed["type"] != "enum" and typed["type"] not in TYPES:
                out.append("field %s: the schema names a type this checker does not know: %r%s"
                           % (".".join([key] + ([typed["name"]] if "name" in typed else [])), typed["type"], NEW_TO_CHECKER))
    return out


def owner(key, kind, schema):
    modules = [layer for layer in schema["fields"][key]["layers"] if layer in schema["module_keys"]]
    if not modules:
        return "%s is the product's own value; no module sets it" % key
    return "%s is set by the %s module, not by a %s module" % (key, " or the ".join(modules), kind)


def check_module(mod, kind, schema):
    """Problems with one module on its own; the same rules as hpcworker's validate_module."""
    if not isinstance(mod, dict):
        return ["the %s module is not a JSON object" % kind]
    errs = []
    # module_keys names kind and module_version; what each may hold is not in module-schema 1
    if mod.get("kind") != kind:
        errs.append("kind must be %r in a %s module (got %r)" % (kind, kind, mod.get("kind")))
    mv = mod.get("module_version")
    if not (_int(mv) and mv >= 1):
        errs.append("module_version must be a whole number from 1 (got %r)" % (mv,))
    for key in IDS[kind]:
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
    return errs + refused(mod, schema)


def strings(obj, path=""):
    """(where, text) for every string anywhere in OBJ, keys joined with dots and list items by index"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            for found in strings(v, "%s.%s" % (path, k) if path else k):
                yield found
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            for found in strings(v, "%s.%d" % (path, i)):
                yield found
    elif isinstance(obj, str):
        yield path, obj


def refused(mod, schema):
    """what the schema's refused_values forbid in any string of MOD (a credential's shape, from the module
    schema hpcworker publishes after module-schema 1's first copy here; absent, nothing is refused)"""
    errs = []
    for rule in schema.get("refused_values", []):
        rx = re.compile(rule["pattern"])
        errs += ["field %s holds what no module may (%s)" % (where, rule["why"]) for where, text in strings(mod) if rx.search(text)]
    return errs


def missing(site, lab, schema):
    """the fields, and the keys inside an object field, a profile must carry that neither the product
    nor SITE nor LAB sets. An object merges key by key across the layers, so a key counts when any
    layer's object holds it (the merge rule is not in module-schema 1; only "additive" is)."""
    product, out = schema["product"], []
    for key, spec in schema["fields"].items():
        layers = [m[key] for m in (product, site, lab) if key in m]
        if spec.get("required") and not layers:
            out.append(key)
        for sub in spec.get("keys", []):
            if sub["required"] and layers and not any(isinstance(v, dict) and sub["name"] in v for v in layers):
                out.append("%s.%s" % (key, sub["name"]))
    return out


def example_problems(mod):
    """Why MOD, a module under examples/, could reach or describe a real machine: a host or a link that
    is not under a reserved name, a host key, or a measurement. A university that does not exist has
    none of these, so a test that runs on it can never touch the internet by mistake."""
    if not isinstance(mod, dict):
        return []
    errs = []
    for key in HOST_FIELDS:
        host = mod.get(key)
        # a name with no dot is a short name inside the cluster (login1), which no one outside resolves
        if isinstance(host, str) and "." in host and not RESERVED.search(host):
            errs.append("field %s names %r: a synthetic site's hosts sit under a reserved name such as "
                        "university.example (RFC 2606)" % (key, host))
    for where, text in strings(mod):
        for m in LINK.finditer(text):
            host = m.group(1).rsplit("@", 1)[-1]
            if not RESERVED.search(host):
                errs.append("field %s links to %r: a synthetic site's links sit under a reserved name such as "
                            "university.example (RFC 2606)" % (where, host or m.group(0)))
    if mod.get("ssh_host_key"):
        errs.append("ssh_host_key is set: a synthetic site has no host to measure a key from; leave it empty")
    measured = mod.get("egress", {}).get("measured") if isinstance(mod.get("egress"), dict) else None
    if measured:
        errs.append("egress.measured holds %s: nothing is measured at a synthetic site; leave it empty"
                    % ", ".join(sorted(str(k) for k in measured)))
    return errs


def _check_folder(root, top, schema, ids):
    """(problems, number of sites, number of labs) for every module under ROOT/TOP. IDS maps each site id
    and each profile id already seen, in this tree or another, to where it was seen."""
    problems, n_sites, n_labs = [], 0, 0
    sites_dir = os.path.join(root, top)
    example = top == EXAMPLES

    def rel(path):
        return os.path.relpath(path, root).replace(os.sep, "/")

    def module(path, kind):
        mod = read_json(path)
        errs = check_module(mod, kind, schema) + (example_problems(mod) if example else [])
        return mod, ["%s: %s" % (rel(path), e) for e in errs]

    for name in sorted(os.listdir(sites_dir)) if os.path.isdir(sites_dir) else []:
        folder = os.path.join(sites_dir, name)
        if not os.path.isdir(folder):
            continue
        site_path = os.path.join(folder, "site.json")
        if not os.path.isfile(site_path):
            problems.append("%s: no site.json" % rel(folder))
            continue
        try:
            site, errs = module(site_path, "site")
        except ValueError as e:
            problems.append(str(e).replace(site_path, rel(site_path)))
            continue
        n_sites += 1
        problems += errs
        if isinstance(site, dict) and site.get("site") != name:
            problems.append("%s: its site id must be %r, the folder's name" % (rel(site_path), name))
        # a synthetic site never shares an id with a deployment: a consumer that tests both would mix them
        if ("site", name) in ids:
            problems.append("%s and %s both name the site %r" % (ids[("site", name)], rel(site_path), name))
        else:
            ids[("site", name)] = rel(site_path)
        labs = os.path.join(folder, "labs")
        for fn in sorted(os.listdir(labs)) if os.path.isdir(labs) else []:
            lab_path = os.path.join(labs, fn)
            if not fn.endswith(".json"):
                continue
            try:
                lab, errs = module(lab_path, "lab")
            except ValueError as e:
                problems.append(str(e).replace(lab_path, rel(lab_path)))
                continue
            n_labs += 1
            problems += errs
            if not isinstance(lab, dict):
                continue
            if lab.get("lab") != fn[:-5] or lab.get("site") != name:
                problems.append("%s: its lab id must be %r and its site %r, as the path says" % (rel(lab_path), fn[:-5], name))
            # one lab per profile id: hpcworker's compose-all refuses two, and module-schema 1 does not say so
            pid = lab.get("profile")
            if isinstance(pid, str):
                if ("profile", pid) in ids:
                    problems.append("%s and %s both compose profiles/%s.json" % (ids[("profile", pid)], rel(lab_path), pid))
                else:
                    ids[("profile", pid)] = rel(lab_path)
            if isinstance(site, dict):
                for key in missing(site, lab, schema):
                    problems.append("%s: the profile it composes with %s lacks %s, which neither sets"
                                    % (rel(lab_path), rel(site_path), key))
    return problems, n_sites, n_labs


def check_tree(root=None, schema=None):
    """(problems, {tree: (number of sites, number of labs)}) for every module under ROOT/sites and
    ROOT/examples."""
    root = root or ROOT
    schema = schema or load_schema(root)
    bad = schema_problems(schema)
    if bad:
        return ["schema/module-schema.json: %s" % p for p in bad], {SITES: (0, 0), EXAMPLES: (0, 0)}
    problems, counts, ids = [], {}, {}
    for top in (SITES, EXAMPLES):
        found, n_sites, n_labs = _check_folder(root, top, schema, ids)
        problems += found
        counts[top] = (n_sites, n_labs)
    return problems, counts


def main(argv):
    args = argv[1:]
    root = None
    if args[:1] == ["--root"] and len(args) == 2:
        root = args[1]
    elif args:
        sys.stderr.write("usage: python3 tools/check_modules.py [--root DIR]\n")
        return 2
    try:
        problems, counts = check_tree(root)
    except ValueError as e:
        problems, counts = [str(e)], {SITES: (0, 0), EXAMPLES: (0, 0)}
    for p in problems:
        print("ERROR: " + p)
    if not problems:
        print("ok: %d site module(s) and %d lab module(s), and %d synthetic site module(s) and %d lab module(s) "
              "under examples/, match schema/module-schema.json" % (counts[SITES] + counts[EXAMPLES]))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

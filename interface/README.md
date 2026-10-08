# What beethoven-sites offers and takes

This repository follows the Beethoven interface standard,
[INTERFACES.md](https://github.com/OpenSpineConsortium/beethoven/blob/main/INTERFACES.md): another
repository reaches it only through what `interface/INTERFACE.json` declares, at a version, through a
copy pinned to a commit this repository's `main` contains; and what it takes from another is such a
copy too. `tests/test_boundary.py` checks it here (rules 1 to 3), in the same `unittest` run as the
checker's own tests, before every push and in CI.

## Offered: `modules`, version 1 (data)

The site and lab modules, every file under `sites/`:

- `sites/<site>/site.json`, one per university's cluster, and `sites/<site>/labs/<lab>.json`, one per
  lab's deployment there. Ids match the schema's `id_pattern` whole, and a module sits where its ids
  say: a site module's `site` is its folder's name, a lab module's `lab` is its file's name and its
  `site` its folder's.
- What a module carries is what the pinned module schema allows (below), and every module passes
  `tools/check_modules.py` against it before it merges: that is the required check on `main`.
- hpcworker takes this export and version with its `framework/sites/pull.sh`, through `gh` and from
  a commit this repository's `main` contains, into `framework/sites/` (each file at its path below
  `sites/`), and composes `framework/profiles/<id>.json` from it. The modules' values reach every
  other repository, and the grid, only inside those composed profiles.

The version rises with a change a consumer must act on: the layout (where a module sits, what its
files are called) or the keys a module says about itself (`kind`, `module_version`, a lab's `site`,
`lab` and `profile`) and what they mean. A module added, changed or removed within the schema is data
and keeps the version. Nothing else here is offered: `tools/check_modules.py` (its command line and
its messages), the tests and the hook may change in any pull request.

## Offered: `example-modules`, version 1 (data)

The synthetic universities: `examples/<site>/site.json` and `examples/<site>/labs/<lab>.json`, the
module files alone (the export's paths list no README, so a consumer's copy of it holds nothing it may
not keep). They are in the layout of `modules` and pass the same checker, with three rules more
(`example_problems`, and the shared id check in `check_tree`): every host and link under a name
reserved for examples, nothing measured, and no site or profile id that a module under `sites/` has.
`examples/README.md` says what each one varies and what module-schema 1 cannot vary yet.

No repository takes it yet. It is meant for hpcworker's suite (BEE-200): a consumer takes it with a
pull of its own, as rule 3 says, and composes it where its tests run, never into the folder of profiles
it ships; an example in `modules` would be composed into `framework/profiles/` and reach every
client's package, which is why the two exports never share a file (`tests/test_boundary.py`). The
version rises on the same changes as `modules`'s; an example added, changed or removed within the
schema is data and keeps it.

## Taken: hpcworker's `module-schema`, version 1 (schema), into `schema/`

`schema/module-schema.json`, with its record `schema/ORIGIN` (the hpcworker commit, the export and
its version, and each file's sha256). Only `tools/pull_schema.sh` writes them:

```
bash tools/pull_schema.sh [--ref REF]   # REF: main, or a tag or commit hpcworker's main contains
```

It reads GitHub through `gh` and the person's own sign-in, never a checkout of hpcworker, and runs
none of hpcworker's code. It takes only the files hpcworker's own `interface/INTERFACE.json` lists
under the export `module-schema` version 1 at that commit (`interface/sites/module-schema.json`,
which lands at `schema/module-schema.json`), writes `ORIGIN`, and deletes nothing: a file the export
no longer holds is named for a person to remove in a reviewed commit. Then `tools/check_modules.py`
and the tests say whether the modules still pass, and the copy and any module change it needs are
committed together.

Today's copy was taken before hpcworker published its interface: it is what `profile.py
module-schema` printed at hpcworker 68e7e35, a commit on hpcworker's `main`. On 2026-10-07 hpcworker's
`framework/lib/profile.py` was the same on its `main` (818f4a2) and printed the same bytes (sha256
123cf0b0...), equal to the `interface/sites/module-schema.json` its interface pull request publishes.
So `ORIGIN` has no `export` line yet, as the standard allows, and the first pull after hpcworker's
interface merges writes one. Until then the pull refuses, in plain words, because hpcworker's `main`
holds no `interface/INTERFACE.json`.

The two repositories pin each other, which the standard allows only between exports of different
kinds that do not depend on each other's version: hpcworker's schema, this repository's data. A rule
changes in hpcworker first (and raises `module-schema`'s version when a module must change), is
taken here with `tools/pull_schema.sh`, and only then may a module use it; the modules go back to
hpcworker with its `framework/sites/pull.sh`.

## What module-schema 1 does not state yet

Every rule `tools/check_modules.py` applies comes from the pinned schema where the schema states it:
the fields, their types and the layers that may set them (a layer `module_keys` does not name is the
product's, which no module sets), the keys inside an object field, what a profile must carry, the
product's values, the keys a module says about itself, the id pattern and `profile_is_site`. The
checker refuses, before it reads any module, a schema whose module kinds, id match or type names it
does not know (`schema_problems`). What the schema does not state yet is listed here, so hpcworker can
publish it in a later version of the export and the checker can then read it instead of holding it.

Rules the checker holds by hand, as hpcworker's `validate_module` and `compose-all` apply them:

| Rule | Where in `tools/check_modules.py` | What the schema would need to carry |
|---|---|---|
| What each type name admits: `int` is never a boolean, a `*_or_none` type also admits null, `enum` admits a string among the field's `values`; and what `id_match` `"whole"` means | `TYPES`, `type_ok`, `id_ok` | for each type name, the JSON types it admits (or a JSON Schema per field and key) |
| A module's `kind` is its kind (`site` or `lab`) | `check_module` | for each of `module_keys`, its type or its allowed values |
| `module_version` is a whole number from 1 | `check_module` | the same: its type and minimum |
| Which keys are ids, matched against `id_pattern`: a site module's `site`, a lab module's `site`, `lab` and `profile` | `IDS`, `check_module` | which module keys and fields are ids |
| An object field merges key by key across the layers, so a key the profile must carry may come from any layer's object; every other value a later layer sets replaces the earlier one | `missing` | the merge rule beside `additive`, which names only the lists that add up |
| Two lab modules never compose one profile | `check_tree` | that a profile id is composed by one lab module |
| Which fields hold a host name (for the examples' reserved-name rule; a link anywhere is found by its scheme) | `HOST_FIELDS`, `LINK` | a format for each field (host, link, path) |

The layout itself (a site module at `sites/<site>/site.json`, its labs under `labs/`, ids equal to the
path) is this repository's own: it is the shape of the export `modules` above. hpcworker's pull and
`compose-all` read the same layout.

hpcworker's credential rule for a composed profile is in the schema now: hpcworker publishes it as `refused_values` in the module
schema (since its commit ee08fa1), the copy here carries it, and the checker refuses a credential's shape
(`sk-ant-`, `CLAUDE_CODE_OAUTH_TOKEN=`, `setup-token`) in every string of a module before the module
merges (`tests/test_check_modules.py`).

Rules hpcworker applies to the composed profile (`validate` in its `framework/lib/profile.py`, run by
`compose-all` on every profile it writes) that module-schema 1 does not state, so the checker cannot
apply them: a module that breaks one passes the required check here, merges, and is refused only when
hpcworker next pulls the modules.

| Field | hpcworker's rule | What the schema would need to carry |
|---|---|---|
| `login_node_rules.poll_floor_seconds` | at least 60 | a minimum for a key |
| `ssh_port` | 1 to 65535 | a minimum and a maximum |
| `browser_key_days` | 1 to 3650, or null | a minimum and a maximum |
| `login_abandon_s` | 0 (never) or at least 300 | a minimum, with 0 allowed besides |
| `ssh_host_key` | `SHA256:` and 43 base64 characters, or empty | a pattern |
| `ssh_host`, `vpn_portal` | a host name, 1 to 253 of letters, digits, dots and dashes, or empty | a pattern |
| `vpn_help_url`, `grid_account_help_url`, `grid_2fa_help_url` | `https://` with no space or quote, or empty | a pattern |
| `ssh_relay` | `wss://` or `https://` with no space or quote, or null | a pattern |
| `session_title` | at most 64 characters, no quote, backquote, `$`, backslash or control character | a pattern, or a maximum length and the characters refused |
| `shared_install` | absolute, no space or quote, or empty | a pattern |
| `shared_state_dir` (and the product's `claude_config_dir`) | absolute, or starting with `$HOME` | a pattern |
| `node_tmp` | holds `$USER` (or `${USER}`), so users never share a directory | a pattern |
| `node_tmp` | starts with `$TMPDIR` only when `tmpdir_is_node_local` is true | a rule between two fields |
| `scheduler_in_worker` | true only with `scheduler` `slurm` and `runtime` `apptainer` or `singularity` | a rule between fields |
| `image_store.path` | not empty | a minimum length for a key |
| `egress.proxy_env` | only `https_proxy`, `http_proxy` and `no_proxy`, in any case | the keys a free object may hold |
| `binds` | each entry a non-empty path without whitespace | a pattern for a list's entries |
| `restricted_workspaces` | each entry `*` or 1 to 32 of letters, digits, `_` and `-` | a pattern for a list's entries |

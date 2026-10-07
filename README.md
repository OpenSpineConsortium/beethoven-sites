# beethoven-sites

The university site modules of Beethoven: every value that belongs to one university's cluster, or
to one lab's deployment on it, and nothing else. A new university is added by writing a site module
and a lab module here; nothing in the framework's code changes. Beethoven runs Claude Code and is not
an Anthropic product; "Claude" and "Claude Code" are Anthropic's marks, used here to say what it runs;
"Open OnDemand" is the mark of its publisher.

## The three layers

`OpenSpineConsortium/hpcworker` composes each deployment's profile, `profiles/<id>.json`, the file
every Beethoven client and the engine read, from three layers laid down in this order:

| Layer | What it is | Where |
|---|---|---|
| product | Beethoven's own values: the sign-in folder Claude Code starts in and the consent markers beside it, `$HOME` as every worker's first bind, the 60 s poll floor, `/dev/shm` for sockets, the worker defaults, how long a worker waits for the sign-in | hpcworker's `lib/profile.py`; copied into `schema/module-schema.json` as `product` |
| site | a university's cluster, whoever uses it: scheduler, login node and its process cap, partitions and QoS, node-local temp, the container runtime, egress, the portal, the VPN, ssh and its host key, help links | `sites/<site>/site.json` |
| lab | one group's deployment on that cluster: its state folder, its shared copy of the framework, its image and `claude`, its volume binds, its allocation account, the partition its long workers use, a browser key's lifetime | `sites/<site>/labs/<lab>.json` |

Wayne State is the site `wayne` and the lab `oschome`, composed into `profiles/wayne.json`.

## The rules a module follows

- **Data only.** A module picks values; behaviour stays in hpcworker. A university whose scheduler,
  portal sign-in or second factor hpcworker does not support needs a reviewed change there, never
  code here.
- **Each field has an owner.** `schema/module-schema.json` names, for every field of the profile,
  the layers that may set it. A lab module that sets a site's field (`ssh_host_key`), a site module
  that sets a lab's (`shared_state_dir`), and any module that sets the product's own
  (`claude_config_dir`, `consent_markers`) is refused. So is a key the schema does not name, at the
  top or inside an object field (`login_node_rules`, `worker_defaults`, `image_store`, `egress`): a
  module is written by hand, so an unknown key is a typo.
- **How layers combine.** An object merges key by key, `binds` add up (the product's `$HOME`, then
  the site's, then the lab's volumes), and any other value a later layer sets replaces the earlier
  one. Together the product, the site and the lab must set every field and key the profile needs.
- **What a module says about itself** stays out of the profile: `kind` (`site` or `lab`) and
  `module_version` in both; in a lab module, `site` (the site it belongs to), `lab` (its own id, the
  file's name) and `profile` (the id of the composed file). Ids are lower-case letters, digits and
  dashes, and each module sits where its ids say.
- **One lab per site for now.** hpcworker still finds an account's profile by its `site` field, so a
  lab's `profile` is its site's id until accounts name their own profile (Linear BEE-208);
  `profile_is_site` in the schema says which rule is in force.
- **Measured values are dated.** Where a module records what a cluster answered (`egress.measured`,
  a host key, the portal's sign-in), `notes` says when and from where. Never a password, a key, a
  token or an account's private data: a module's values are read by every client and published,
  inside the composed profile, with the framework's shared copy.

## Checking a module

```
python3 tools/check_modules.py                   # every module against schema/module-schema.json
python3 -m unittest discover -s tests            # the checker's own tests and the boundary's (tests/test_boundary.py)
```

Python 3.6 standard library, nothing else, and nothing of hpcworker imported: whoever writes a
module checks it with this repository alone. The checker sees each module and each site and lab pair,
with every rule the pinned schema states; what the schema does not state yet is listed in
`interface/README.md`. The composed profile's value rules (a host key's form, a link being https, the
poll floor's minimum, no credential-shaped text) are in no schema yet and are checked only by
hpcworker when it composes what it pins (`profile.py compose-all --check`), so a module that passes
here can still fail there.

## How the schema and the modules move between the two repositories

Each repository reaches the other only through what it declares in `interface/INTERFACE.json`, as a
copy pinned to a merged commit and taken through `gh`, never from a checkout (the interface standard;
`interface/README.md` says what this repository offers and takes).

- **The schema comes from hpcworker.** `bash tools/pull_schema.sh [--ref REF]` takes hpcworker's
  export `module-schema` version 1 from GitHub at a commit hpcworker's `main` contains, runs none of
  hpcworker's code, and writes `schema/module-schema.json` and `schema/ORIGIN` (the commit, the export
  and its version, and the file's sha256; `tests/test_boundary.py` checks the copy against it). A rule
  changes in hpcworker first, then lands here before a module may use it. Until hpcworker's `main`
  publishes its `interface/INTERFACE.json`, the pull refuses and says so.
- **The modules go to hpcworker.** This repository's export `modules` version 1 is every file under
  `sites/`. hpcworker keeps a pinned copy in `framework/sites/` with its own `ORIGIN` (this
  repository's commit and each file's sha256); its `framework/sites/pull.sh` copies them through
  `gh`, `profile.py compose-all` writes the profiles, and the copy and the profiles are committed
  there together. Its suite fails while a profile differs from what its modules compose.

## Pull requests

The checks decide what lands, with no human review step: `.githooks/pre-push` runs the checker and
the tests before a push (point git at it once with `git config core.hooksPath .githooks`;
`SKIP_GATE=1` skips it knowingly, and the commit says why), `.github/workflows/ci.yml` runs them on
Python 3.6 and the current Python, `.github/rulesets/main.json` makes that job the required check
on `main` (applied by `rulesets.yml`), and `automerge.yml` arms auto-merge on each pull request.
Pull requests open ready for review, never as drafts.

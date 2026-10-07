# beethoven-sites — working context

The university site modules of Beethoven: data only, one site module per university's cluster and
one lab module per group's deployment on it (`README.md`). greg decided on 2026-10-05 (00:59Z, Linear
BEE-221) that the modules have their own repository; the design is the Linear project
*U — University Site Modules* (BEE-198 to BEE-222) and `/mnt/project-files/sites/DESIGN.md` in the
project's files. `OpenSpineConsortium/hpcworker` owns the schema, the rules and the composing; this
repository pins its schema (`schema/`) and hpcworker pins these modules (`framework/sites/` there).

Beethoven runs Claude Code and is not an Anthropic product; "Claude" and "Claude Code" are
Anthropic's marks, used here to say what it runs; "Open OnDemand" is the mark of its publisher.

## Rules that are not negotiable

hpcworker's `CLAUDE.md` holds the launcher's rules, and they bind here too. The ones a module touches:

- **No API key anywhere** (greg, 2026-10-04 13:27Z: "no api key anywhere thats the only fundamental
  rule of this software"), and no usage credits. No module names a key, a gateway
  (`ANTHROPIC_BASE_URL`), a cloud provider route or a credential; Beethoven signs in only with a
  Claude subscription.
- **Never a Claude credential, a password, a token or a secret** in a module, a commit, a log or an
  argv. A module's values are read by every client and published, inside the composed profile, with
  the lab's shared copy of the framework. The student's sign-in folder (`claude_config_dir`) and the
  consent markers are the product's own values and no module may set them.
- **Data only, no code.** No module carries a script, a command to run or anything a client would
  execute. Behaviour belongs in hpcworker, in a reviewed change.
- **Attribute and date what was measured**, and keep it apart from what is declared: `notes` says
  when and from where a value was observed. "Not yet measured" is the honest form.
- **Grid etiquette** is hpcworker's and the clients' to follow; a module only states a site's rules
  (its login node's process cap; the 60 s poll floor is the product's and a site may only raise it).
- The Beethoven name and the trademark sentence above stand wherever the product is described.
  Never use the word that starts "prov" and ends "enance" for the history of a file or data; say
  origin, source or record. Versions are integers.

## Working here

```
python3 tools/check_modules.py                     # every module against the pinned schema
python3 -m unittest discover -s tests              # the checker's tests and the boundary's
bash tools/pull_schema.sh [--ref REF]              # take hpcworker's export module-schema from GitHub (REF: main)
git config core.hooksPath .githooks                # once per checkout: the checks run before every push
```

A change to a module: edit it, run the checker and the tests, open a pull request (ready, never a
draft); the required check decides and auto-merge lands it. Then hpcworker takes it with
`framework/sites/pull.sh` and `profile.py compose-all` in a pull request of its own. A change to what
a module may carry is made in hpcworker first (`FIELD_LAYERS`, `SUBFIELDS`, `PRODUCT` in
`framework/lib/profile.py`, published as its export `module-schema`), merged there, then pulled here
with `tools/pull_schema.sh`.

This repository is sealed (the interface standard; `interface/README.md`): `interface/INTERFACE.json`
declares what it offers (the export `modules`, every file under `sites/`) and what it takes
(hpcworker's `module-schema` into `schema/`), and `tests/test_boundary.py` fails on a line that reaches
another repository's checkout, on a copy that differs from its `ORIGIN`, and on a manifest out of
form. Nothing here reads, runs or copies a file of another checkout; the schema is taken only by
`tools/pull_schema.sh`, through `gh`, from a commit hpcworker's `main` contains, and never edited by
hand. `tools/check_modules.py` takes every rule the schema states from the schema; what it holds by
hand, and the composed profile's rules no schema states yet, are listed in `interface/README.md`.

Every unit of build work appends one row to `/mnt/project-files/ledger/LEDGER.md` when the project's
files are reachable (format in `ledger/README.md`); re-read it just before appending.

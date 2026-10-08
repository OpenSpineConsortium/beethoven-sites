# Synthetic universities

The modules here describe universities that do not exist. They are never a deployment: no student
uses one, no lab hosts one, and no profile of theirs ships in any Beethoven package. They are here so
that every consumer's tests can run once per module, beside the real deployments in `sites/`, and a
test or a line of code that works only for Wayne State shows itself (Linear BEE-200,
`sites/DESIGN.md` section 5.3 in the project's hub).

They are offered as their own export, `example-modules` (`interface/INTERFACE.json`), never as part of
`modules`: hpcworker composes the profiles every client ships from `modules` alone, so a consumer
that wants an example takes `example-modules` on purpose and composes it where its tests run, never
into its `profiles/`.

## The rules an example follows

Every rule of a deployment's module (`tools/check_modules.py`, the same layout, the same schema), and
three more, which the checker applies under `examples/` only:

- **It names no real machine.** Every host and every link sits under a name reserved for examples
  (RFC 2606 and RFC 6761: `.example`, `.test`, `.invalid`, `.localhost`, `example.com`, `example.net`,
  `example.org`), or is a short name with no dot (`login1`), which only a cluster's own resolver
  answers. A test that runs on it cannot reach the internet by mistake.
- **Nothing in it is a measurement.** No host key, nothing under `egress.measured`: no machine was
  asked, so nothing is recorded as its answer. Its `notes` say it is synthetic.
- **It shares no id with a deployment**: no site id and no profile id of `sites/`, so a consumer that
  composes both never gets two profiles of one name.

## `example`: Example University

`example/site.json` and `example/labs/demo.json`, composed into the profile `example`. It differs
from Wayne State in every field both set, but three: `kind` and `module_version`, which say what the
file is, and `scheduler`. It keeps Slurm, since the PBS and LSF adapters have fixture tests of their
own in hpcworker. `tests/test_check_modules.py` holds it to that.

| Where a site differs | Wayne State (`sites/wayne`) | Example University |
|---|---|---|
| QoS | `secondary`, `requeue` | none |
| allocation account | none | `demo-alloc`, on every job |
| node-local temp | `/tmp/$USER/...`; `$TMPDIR` is CephFS | `$SLURM_TMPDIR`, and `$TMPDIR` may be trusted as node-local |
| container runtime | Apptainer, through `module load` | Singularity on the `PATH`, no module |
| runtime cache | under the node's temp | its own folder on the node's temp |
| home filesystem | Panasas | Lustre |
| internet from a compute node | direct, measured | through a proxy that the module `proxy/1` sets, with the university's CA bundle |
| portal sign-in | HTTP basic | a cookie |
| VPN | GlobalProtect, required | none |
| ssh | port 22, host key measured, no relay | port 2222, no key (nothing to measure), a relay |
| login node | 20 processes, the 60 s poll floor | 50 processes, a 120 s floor (a site may only raise it) |
| scheduler inside the worker | bound in | not |
| `XDG_RUNTIME_DIR` fix | on | off |
| the framework | the lab's shared copy | each student's own copy |
| image | a sandbox folder | a SIF file |
| worker size | the product's (2 CPUs, 8G, 8 h) | 4 CPUs, 16G, 12 h |
| sign-in wait, browser key | the product's 1200 s, no expiry | 900 s, 30 days |

What module-schema 1 cannot say yet, so this example cannot vary it: that the second factor is Duo
(the extension's sign-in words, BEE-213), that access is granted by a Unix group rather than a named
list (hpcworker's access tools, BEE-205), that the scheduler refuses a job with no account, and where
each of the login node's rules comes from (BEE-206). Each lands in hpcworker's schema first and then
here.

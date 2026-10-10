# Research assets

Owner: Development, individual unassigned, working with Development on one optional
optimization after the ordinary product baseline is measured.

This folder is for future approved training notebooks, evaluation notebooks,
and experiment configuration. The former notebooks were intentionally removed;
this scaffold does not restore them.

Keep runtime implementation under `icare_app/` and repeatable evaluation commands
under `tools/`. Before committing a notebook, clear cell outputs and verify that
it contains no credentials, private media, or local dataset paths that should
not be shared. Record the dataset/split version and validation procedure in
project docs. Store checkpoints and generated experiment outputs in ignored
`artifacts/` or external storage.

Use `evaluation/` for repeatable baseline/product measurements and this folder
for optional model/compute experiments. A controller, paper, patent, or extra
behaviour must not delay the example/upload release or be claimed as implemented
without evidence. See the [measurement contract](../docs/interfaces/metrics.md).

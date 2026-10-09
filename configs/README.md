# Product configuration boundary

Person 5 coordinates environment/origin/job limits for the
[default stack](../docs/project/stack.md). The API reads `ICARE_*` variables
(`api/config.py`, `api/engine.py`); `deployment/compose.yaml` passes them through.
Persons 1/4 own model/preprocessing/threshold meaning and Persons 2/5 own
ownership/limits/retention.

The root .env.example contains planned engine variable names; retained libraries
do not automatically load it. The removed launcher no longer wires environment
settings. Implement validation and startup against the actual engine/API/frontend,
not old Gradio options. Keep real secrets in the host store.

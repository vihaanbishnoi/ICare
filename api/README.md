# API jobs and incidents

Person 2 builds a fresh FastAPI service under /api/v1. No endpoints are implemented
yet. Read [Person 2](../docs/team/person_2.md),
[API v1](../docs/interfaces/api.md), [engine v1](../docs/interfaces/inference.md),
[stack](../docs/project/stack.md), and the [starter prompt](../docs/team/prompts/person_2.md).

Implement isolated bounded jobs, real result progress/errors, incidents, owned
media/reports, cancellation, SQLite metadata, and cleanup. Person 1 supplies the
injectable engine; Person 3 consumes the documented fields; Person 5 integrates hosting.

Old UI/upload callbacks were removed. Do not wrap them or expose predictable
report paths. Development engine adapters are for tests and must not make the
public service appear model-ready. Keep the same route/field contract across fixtures
and the actual implementation.

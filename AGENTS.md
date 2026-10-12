# ICare development instructions

Follow the current request. During mentoring or read-only audits, read the source,
explain actual behavior and pause at the requested checkpoints. Do not edit,
execute project code or deploy unless requested.

Keep changes focused. Preserve trained weights, class order, preprocessing and
threshold meaning unless measured validation justifies a change. Update API
schemas and their consumers together. The runtime entry points are
api.main:create_app and icare_app.engine.load_engine; the README describes setup.

Use the existing CPU/FastAPI/React stack. Do not restore Gradio, legacy global
sessions, LLM inference, mandatory webcam workflows or team handoff material.
Do not recreate academic reports or planning-document collections unless requested.

Run affected tests and python -m tools.check_repository. For frontend changes,
run npm test, npm run build and npm run lint. Use requirements-test.txt in a
separate test environment. Distinguish synthetic adapters from real model evidence.

Keep secrets, private videos, datasets, caches and generated outputs out of Git.
Historical metrics are group-aware, not verified subject-independent. Do not
invent permissions, accuracy, preprocessing parity, latency or novelty. Keep
public documentation factual and concise, without personal work plans or role assignments.

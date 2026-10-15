# Documentation convention

Documentation is organised by feature, not by document type. A document lives with the feature it
describes, so its design, its delivery evidence and its operating guidance stay together.

```
docs/<feature>/
├── README.md      the index: every document in the feature is listed here
├── design/        contracts, designs, plans, decisions
├── evidence/      verify reports, build records, run records, measurements
└── guides/        runbooks, walkthroughs, reader-facing operational material
```

Cross-cutting material (conventions, architecture-wide background) lives at `docs/` root or under
`docs/_cross/`. A document that concerns one feature belongs in that feature's folder even if other
features refer to it.

Rules:

1. Every new document lands in a feature folder, and that folder's `README.md` is updated in the same change.
2. Do not create flat `plans/`, `specs/` or `notes/` buckets.
3. Move documents with `git mv` and fix inbound links in the same change.
4. Numbers in evidence documents are the observed output of a named command. Never assumed, never copied forward.
5. Dated files use `YYYY-MM-DD-<topic>.md`.

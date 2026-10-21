## What this changes

<!-- The behaviour that is different afterwards. -->

## Why

<!-- What was wrong, or what this makes possible. If it is a fix, how it was
found matters as much as what it was. -->

## Checks

- [ ] `make check` passes
- [ ] If a published number moved: `make bench` and `make report` were rerun and
      the regenerated files are in this pull request
- [ ] If a detector was added or changed: it declares a `blind_to`, and the
      claim is demonstrated by a test rather than asserted in the docstring
- [ ] If a new parameter was added: it is either sourced in `docs/sources.md`
      or declared a choice in the benchmark's conditions block
- [ ] Nothing under `src/` opens a socket
- [ ] No em dashes or en dashes anywhere, including this description

# legacy/ — pre-retrofit safety archive

Files in this directory are **NOT** loaded at runtime. They exist as
known-good fallbacks if a regression is discovered post-merge of the
Phase 3B commons retrofit.

Per `commons/docs/ui-platform-baseline-v1/MIGRATION_RULES.md` §
"Local backup QSS strategy", these files are removed in a follow-up
PR ~30 days after the retrofit ships (assuming no regressions).

## Contents

| File | Origin | Removal target |
|------|--------|----------------|
| `phoenix_style.qss.preretrofit` | The repo-root `phoenix_style.qss` shipped with Phoenix Valve Checkout Tool through v1.7.0, copied unchanged when the Phase 3B commons retrofit landed. 110 selectors — effectively a subset of commons's 114-selector canonical QSS (commons adds Phoenix-CAD-specific `#comToggleBtn` variants that don't apply to Checkout widgets). Same Phoenix System A dark navy + red + blue palette. | ~30 days after Phase 3B merges (per MIGRATION_RULES.md). |

## Do not edit

Files here are immutable snapshots. Edits would defeat the
"known-good fallback" purpose. If you need to modify the canonical
QSS, edit `commons/src/phoenix_commons/theme/phoenix_style.qss`
(through a commons PR) and re-pin the submodule.

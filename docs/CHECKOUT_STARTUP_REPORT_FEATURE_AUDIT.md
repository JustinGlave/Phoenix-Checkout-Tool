# Phoenix Checkout — Startup Report Export Feature Audit

**Date:** 2026-06-16
**Phase:** Audit + implementation plan only — **no code written, nothing built or released.**
**Inputs:**
- `Startup Report - App Integration Spec.md`
- `PHOENIX STARTUP REPORT_SiteName_v2.0.xlsx` (v2.0 template, inspected directly with openpyxl 3.1.5)

**Goal:** Determine how the Phoenix Checkout Tool can populate the Startup Report workbook from existing job/checkout data — what maps, what's missing, where the button lives, how to bundle the template, and whether the exe-only updater blocks a safe release.

> **Guardrail context:** `PROJECT_REVIEW.md` findings are known. This task uses them **only as guardrails** (especially the exe-only updater / template-packaging risk). It is **not** a remediation sprint.

---

## 0. Headline conclusions

1. **The recommended approach is sound and de-risked.** I empirically verified that `openpyxl.load_workbook(template) → write values → save` preserves *everything* the template owns — the three dropdowns, the PASS/FAIL conditional formatting, all 25 merged ranges, the hidden L–AE outline group, the print area + repeat-header row, the column-A auto-number formulas, the legend, the Cover formulas, and written-cell styling. We do **not** need to rebuild any styling. (Test details in §3.4.)
2. **The Startup Report is a JOB-level artifact, but Checkout stores its metadata at the CHECKOUT (record) level.** Project, Technician, ATS Job #, Date, Description all live on each `ValveCheckout`, not on the `Job`. The report's metadata block must therefore be *aggregated* from records or *entered once* at export time. This is the single biggest design decision.
3. **Several Startup Report fields have no source in Checkout today:** Site Name, Building, Floor, Location/Room, Executive Summary, and a numeric Face Velocity (FPM). None are blockers — they can be blank-for-v1 or collected via a small export-time dialog.
4. **The valve-type taxonomy doesn't line up 1:1.** Checkout has 9 valve types; the Startup Report dropdown has 4 (`Supply / General Exhaust / Fume Hood / PBC`). Five Checkout types map ambiguously — **operator must confirm** (no silent invention).
5. **The exe-only updater can safely ship the *code*, but not a new external *template file*.** If the template is bundled as a normal data file (the obvious choice), existing auto-updated installs will get the new code but **not** the template, and the feature will fail until they reinstall. Embedding the template bytes in source (precedent: the QSS embed in commit `e7c14d9`) sidesteps this without touching the updater.

**Overall recommendation: READY AFTER DECISIONS** (see §10). No STOP condition is hard-triggered — every gap has a safe default — but the feature shouldn't be built until the operator settles the mappings, the metadata-sourcing model, and the packaging choice.

---

## 1. Current repo / release state

| Item | State |
|---|---|
| Version | `version.py` → `1.7.0` |
| Branch | working in worktree `claude/pedantic-euler-0e7317` (this audit is a doc, not a code change) |
| Export engine | `checkout_export.py` — `export_records()` is the single public entry; per-valve-type fill functions; openpyxl 3.1.5 |
| Existing templates | `checkout_template.xlsx`, `template_gex.xlsx`, `template_mav.xlsx`, `template_cscp_fh.xlsx`, `template_pbc_room.xlsx` — bundled **flat** via `build.bat:32-39` `--add-data="…;."`, resolved at runtime by `_resource_path()` (`_MEIPASS` when frozen, else source dir) |
| Updater | `updater.py` — GitHub release zip; **exe-only** (`build.bat:83` zips only the exe; `updater.py:183` copies only `EXE_NAME` over the install) |
| Build | PyInstaller `--onedir` (`build.bat:27`) → exe + `_internal/` payload (templates live in `_internal/`) |
| Relevant guardrails | `PROJECT_REVIEW.md` §2.2 (exe-only update doesn't refresh `_internal/`), §2.1 (unsigned update chain) |

> Note: the source-of-truth template folder (`C:\Users\justing\Projects\Phoenix Documentation\`) also contains renamed copies (`template_celeris_fh.xlsx`, `template_celeris_gex.xlsx`, `template_celeris_mav.xlsx`, `template_cscp_fh.xlsx`, `template_cscp_pbc.xlsx`) and a `PHOENIX CHECKOUT_SiteName_v1.0.xlsx`. These differ from the names the repo currently bundles — **out of scope** for this feature, but worth reconciling separately.

---

## 2. Current data availability (Checkout model)

Source: `checkout_tool_backend.py` (dataclasses) + `checkout_tool_gui.py` (field widgets) + `checkout_export.py` (dict-key schemes).

**`Job`** (`checkout_tool_backend.py:27`): `id`, `job_number`, `job_name`, `archived`. *(No project/site/building/floor/technician at the job level.)*

**`ValveCheckout`** (`checkout_tool_backend.py:39`):
- Header: `valve_tag`, `project`, `ats_job_number`, `date` (ISO `yyyy-MM-dd`), `technician`, `description`, `model` (default `"CELERIS 2"`), `valve_type` (default `"Fume Hood"`), `pass_fail` (`""`/`"Pass"`/`"Fail"`), `emer_min`, `valve_min_sp`, `valve_max_sp` (all SP fields validated `QIntValidator(0,99999)` — `checkout_tool_gui.py:1597-1603`)
- `wiring` dict, `sash_sensor_mounted` (bool)
- `config` dict — keys `{row}_cfm` / `{row}_notes` for rows `valve_min, valve_max, sched_min, sched_max, hood_sash_min, hood_sash_max` (`CONFIG_ROWS`, `checkout_tool_gui.py:251`)
- `verification` dict — keys `{row}_result` / `{row}_notes` for rows `face_velocity, sash_height_alarm, sash_sensor_output, low_flow_alarm, jam_alarm, emergency_exhaust, mute_function` (`VERIFY_ROWS`, `checkout_tool_gui.py:260`). **Each `_result` is a dropdown `""/Pass/Fail/N/A`** (`checkout_tool_gui.py:1879`) — *not a number.*
- `notes` (free text, multi-line)

**Valve types** (combo, `checkout_tool_gui.py:1580`): `Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet, CSCP Fume Hood, PBC Room`.

**Model defaults** (`_MODEL_DEFAULTS`, `checkout_tool_gui.py:2957`): Celeris types → `CELERIS 2`; `CSCP Fume Hood` → `ACM (CSCP)`; `PBC Room` → `PBC (CSCP)`. *(This corroborates the product-line derivation in §3.)*

**Not present anywhere in the model:** site name, building, floor, location/room, executive summary, numeric face velocity (FPM), explicit product-line field.

---

## 3. Startup Report field mapping

Template facts verified directly: metadata labels in col A (`A3` Project … `A11` Description), **values written to `C3`–`C11`** (merged `C3:F3`…`C11:F11`); Executive Summary value to `G4` (merged `G4:K11`); valve table header row 14, data rows 15–54 (40 preformatted); dropdowns `C15:C54="CSCP,Celeris"`, `E15:E54="Supply,General Exhaust,Fume Hood,PBC"`, `G15:G54="PASS,FAIL"`; CF on `G15:G54`; hidden group `L:AE`; print area `A1:K56`; legend at row 56.

**Confidence legend:** **A** = already available · **B** = derivable safely · **C** = missing, user-entered · **D** = missing, blank for v1 · **E** = ambiguous, operator decision.

### 3.1 Metadata block (job-level)

| SR cell | Field | Class | Proposed source | Notes |
|---|---|---|---|---|
| `C3` | Project | **B/E** | `Job.job_name` *or* common `record.project` | Report is job-level; pick one source. Records usually share `project`. |
| `C4` | Site Name | **C** | — | Not in model. Collect at export time or leave blank. |
| `C5` | Building | **C** | — | Not in model. |
| `C6` | Floor | **C** | — | Not in model. |
| `C7` | Technician | **B** | `record.technician` (aggregate) | Per-checkout; use most-common / first, or join distinct names. |
| `C8` | ATS Job Number | **A/B** | `Job.job_number` *or* `record.ats_job_number` | Prefer the job-level `Job.job_number`. |
| `C9` | Date of Checkout | **B** | `record.date` (aggregate) | Per-checkout; use latest or a range. String or date both render fine (spec §27). |
| `C10` | Product Line(s) | **B** | derive from the job's valve types | `CSCP` if any CSCP/PBC; `Celeris` if any Celeris; `CSCP & Celeris` if mixed. |
| `C11` | Description | **D/E** | (blank) or `Job.job_name` | Per-checkout in model; ambiguous at job level. Cover does **not** echo C11. |
| `G4` | Executive Summary | **C/D** | (blank) or export-time text box | Not in model. Could prompt once at export. |

### 3.2 Valve rows (one row per checkout record, starting row 15)

| Col | Field | Class | Proposed source | Notes |
|---|---|---|---|---|
| `A` | # | — | **do not write** | Template auto-numbers via `=IF(B{r}="","",ROW()-14)`. |
| `B` | Valve Tag # | **A** | `record.valve_tag` | Free text. |
| `C` | Product Line | **B** | derive: `CSCP` if `valve_type ∈ {CSCP Fume Hood, PBC Room}`, else `Celeris` | Matches dropdown + model defaults. |
| `D` | Model | **A** | `record.model` | Free text; e.g. `CELERIS 2`, `ACM (CSCP)`, `PBC (CSCP)`. |
| `E` | Valve Type | **E** | see §3.3 | 9→4 taxonomy; 5 types ambiguous. **Operator must confirm.** |
| `F` | Location / Room | **C/D** | (blank) or export-time entry | Not in model. |
| `G` | Pass/Fail | **B** | `record.pass_fail` → uppercase | See §3.3 (unambiguous). |
| `H` | Valve Min (CFM) | **B/E** | `record.valve_min_sp` (recommended) *or* `config["valve_min_cfm"]` | Header SP is a validated number; config CFM is the config-table value. Pick one. PBC Room hides SP fields → blank. |
| `I` | Valve Max (CFM) | **B/E** | `record.valve_max_sp` (recommended) *or* `config["valve_max_cfm"]` | Same as H. |
| `J` | Face Velocity (FPM) | **D** | (blank) | **No numeric source.** `verification["face_velocity_result"]` is `Pass/Fail/N/A`; `face_velocity_notes` is free text (unsafe to parse). |
| `K` | Notes | **A** | `record.notes` | Multi-line OK in one cell. Consider trimming to keep print tidy. |
| `L`–`AE` | Detailed readings | **D** | (blank) | Checkout has no structured Voltage/Damper/etc. fields. Hidden group; don't print by default. Leave blank for v1. |

### 3.3 Required value mappings (no silent invention)

**Pass/Fail → `G` (`PASS`/`FAIL`)** — *unambiguous, not a STOP condition:*
- `"Pass"` → `"PASS"`
- `"Fail"` → `"FAIL"`
- `""` (unset) → **leave blank** (do not write; col A stays blank, CF leaves it uncolored)
- (`record.pass_fail` only ever holds `""`/`Pass`/`Fail` — `checkout_tool_gui.py:1594`.)

**Product Line → `C` (`CSCP`/`Celeris`)** — *derivable safely (B):*
- `CSCP` ← `valve_type ∈ {CSCP Fume Hood, PBC Room}`
- `Celeris` ← `valve_type ∈ {Fume Hood, GEX, MAV, Snorkel, Canopy, Draw Down Bench, Gas Cabinet}`

**Valve Type → `E` (`Supply`/`General Exhaust`/`Fume Hood`/`PBC`)** — *partly ambiguous (E):*

| Checkout `valve_type` | Proposed `E` value | Confidence |
|---|---|---|
| Fume Hood | `Fume Hood` | High |
| CSCP Fume Hood | `Fume Hood` | High |
| PBC Room | `PBC` | High |
| GEX | `General Exhaust` | Medium (GEX = "general exhaust") |
| MAV | **? (Supply?)** | **Ambiguous — confirm** |
| Snorkel | **? (General Exhaust?)** | **Ambiguous — confirm** |
| Canopy | **? (General Exhaust?)** | **Ambiguous — confirm** |
| Draw Down Bench | **? (General Exhaust?)** | **Ambiguous — confirm** |
| Gas Cabinet | **? (General Exhaust?)** | **Ambiguous — confirm** |

Default for any unconfirmed type: **leave `E` blank** (never write a value that isn't in the dropdown list). This is *not* a hard STOP (the feature can ship with blanks), but the spec forbids inventing mappings — so the 5 ambiguous rows need an explicit operator ruling before they're populated.

### 3.4 Style-preservation verification (empirical)

Ran `load_workbook(v2.0) → write C3/C8/C9/G4 + 2 valve rows (cols B–K) → save → reload`. Confirmed preserved in the output:
- 3 data validations (`C/E/G`) with exact ranges and lists
- Conditional formatting `G15:G54` (PASS `dxfId 0`, FAIL `dxfId 1`)
- 25 merged ranges incl. `G4:K11`
- `L` and `AE` still `hidden=True, outlineLevel=1` (the collapsed group survives)
- print area `A1:K56`, repeat-header `$14:$14`, landscape, fit-to-width
- column-A formulas (`A15`, `A40`) intact
- legend row 56 intact
- Cover formulas intact and untouched
- written values present (incl. numeric `H15=120`) and styled (Calibri, thin borders)

**Conclusion:** the spec's "load template, write values, save" approach is safe for this template on openpyxl 3.1.5. (Still worth locking in with the SR-5 tests in §8, since openpyxl preservation is template-dependent.)

---

## 4. Export-system integration recommendation

**Current export surface** (`checkout_tool_gui.py`):
- File menu: "Export to Excel…" (`:1039`) and "Export All Checkouts to Excel…" (`:1042`)
- Tree context menu: "Export to Excel…" (`:2310`) and "Export All Checkouts to Excel…" (`:2280`)
- Handlers `_export_checkout` (`:2761`) and `_export_job` (`:2787`) → `export_records(...)`; both gate on `_check_export_issues` (`:2823`), then `QFileDialog.getSaveFileName` (user picks path each time — no remembered output folder), then a success/critical message box. Default names: `"{valve_tag}.xlsx"` / `"{job_number or job_name} Checkouts.xlsx"`.

**Recommendation — smallest sensible addition:** the Startup Report is inherently **job-level**, so add a single new entry that mirrors `_export_job`:
- **File menu item:** "Export Startup Report…" (next to the existing two export items)
- **Job context-menu item:** "Export Startup Report…" (next to "Export All Checkouts to Excel…")
- Both call one new handler (e.g. `_export_startup_report(job_id)`), tied to the **currently selected job**, reusing the existing `getSaveFileName` + try/except + message-box pattern. Default name e.g. `"{job_number or job_name} — Startup Report.xlsx"`.

Keep it **separate from `export_records`** — that function is the per-checkout-sheet engine and shouldn't be entangled with the single-workbook Startup Report writer. The new export should be its own small function/module (§6, SR-2). Do **not** rewrite the existing export system.

---

## 5. Template packaging analysis

The feature needs the Startup Report template available at runtime. Options:

| Option | Description | Updater-safe (exe-only)? | Verdict |
|---|---|---|---|
| **A** Bundle beside existing templates (`--add-data="…;."`) | One more flat data file in `_internal/` | ❌ existing auto-updated installs won't receive it | Familiar, but breaks exe-only clients (see §6) |
| **B** `templates/` subdir + add-data | Same as A, organized | ❌ same problem | Same risk as A |
| **C** Embed template bytes in source (e.g. base64 in a `.py`, load via `BytesIO`) | Template travels *inside the exe* | ✅ delivered by exe-only auto-update | **Recommended** for updater-safety without touching the updater |
| **D** User-selected template path | Prompt for the `.xlsx` each time | ✅ (no bundling) but poor UX/fragile | Only as a fallback |
| **E** Installer-only / manual release | Ship via new `Setup.exe` / FullInstall.zip; require reinstall | ✅ (full bundle) | Clean, but forces a reinstall for every user |

**Why C works:** the template is ~12 KB. openpyxl can `load_workbook(BytesIO(raw_bytes))`, so embedding the bytes (base64 constant) lets the writer load from memory — no `_internal/` file needed. The new code *and* the embedded template both ride inside the exe, which exe-only auto-update **does** deliver. There is direct precedent: commit `e7c14d9` ("Embed full QSS as Python fallback for auto-update compatibility") did exactly this for the stylesheet, for exactly this reason.

**Recommendation:** **Option C** (embed) as the primary, with **Option E** (installer-only first release) as the conservative alternative if embedding binary bytes in source is undesirable. Avoid A/B until/unless the updater is changed to ship the full bundle (out of scope here).

---

## 6. Exe-only updater risk analysis

**Does the feature add a dependency?** No. openpyxl is already bundled; the writer uses only stdlib + openpyxl. So this feature does **not** trigger `PROJECT_REVIEW.md` §2.2's "dependency bump bricks the install" failure mode. The new **code** ships safely via the existing exe-only auto-update.

**The only delivery gap is the template file.** With the exe-only updater:
- New exe (with the feature code) **is** delivered to auto-updated clients. ✅
- A new external template in `_internal/` is **not** delivered (the update copies only the exe; `_internal/` stays frozen at install time). ❌
- Result if bundled as data (A/B): auto-updated clients run code that references a missing template → `FileNotFoundError` at export (the existing `_load_template` guard raises a "reinstall to restore templates" message, `checkout_export.py:531`). The feature is **broken for those users until they reinstall.**

**Answers to the required questions:**
- *Can the exe-only updater safely deliver this feature?* **Yes — if the template is embedded (Option C)** or shipped via installer (E). **No** if the template is a new external data file (A/B).
- *Should the first release be installer-only?* Optional. Embedding (C) removes the need; installer-only (E) is the conservative fallback.
- *Is a full-folder updater transition required?* **No** for this feature, if Option C is used. (The full-folder transition is the proper long-term fix from `PROJECT_REVIEW.md`, but it's explicitly out of scope here — **do not change the updater**.)
- *Does embedding avoid the immediate updater problem?* **Yes** — it's the whole point of Option C.

**Guardrail honored:** no updater/build/installer change is proposed in this phase.

---

## 7. More-than-40-valves plan

**Can a job exceed 40 valves?** Yes — `records_for_job` (`checkout_tool_backend.py:185`) has no cap, and a real building wing can easily exceed 40 valves. The template ships 40 preformatted rows (15–54), legend at row 56, print area `A1:K56`.

**Two paths:**

**v1 (recommended): cap at 40 with an explicit warning.** If a job has >40 records, warn the user (e.g. "This job has N valves; the Startup Report template fits 40. Export the first 40, or split the job?") and either export the first 40 or abort. Safe, simple, no fragile template surgery. The `_check_export_issues` pattern is a natural place for the warning.

**v1-stretch / v2: extend the table** (per spec §60-67), in this order, before saving:
1. For each new row `r` (55, 56, …), copy a data row's full per-cell style (`copy.copy(cell._style)` from row 15/54).
2. Set `A{r} = "=IF(B{r}=\"\",\"\",ROW()-14)"` (the one place we write a formula, matching the template's own).
3. Extend the CF range `G15:G54` → `G15:G{last}` and the dropdowns `C/E/G` `sqref` to the new rows.
4. Extend print area `A1:K56` → `A1:K{last+2}` and move the legend row (currently row 56, merged `A56:D56` + `G56:K56`) below the new data.

**Risk:** Medium. Editing CF ranges, DV `sqref`, merged-cell relocation, and per-cell style copies via openpyxl is fiddly and easy to get subtly wrong (merge conflicts, CF priority, outline state). Given the round-trip-preservation success in §3.4, the *un-extended* path is low-risk; the *extension* path needs its own focused tests (§8). **Recommendation: ship v1 capped at 40 with a clear warning; implement extension as a fast-follow once the core export is proven.**

---

## 8. Proposed implementation sequence (surgical)

> All steps are **planning targets** — not yet implemented.

- **SR-1 — Mapping helper (no UI).** A pure module (e.g. `startup_report_export.py`) with: product-line derivation, pass/fail uppercasing, valve-type→E mapping table (with the 5 ambiguous entries driven by confirmed decisions), and job-level metadata aggregation (project/technician/date/ATS#). No Qt, unit-testable in isolation.
- **SR-2 — Export function.** `export_startup_report(job, records, output_path, meta_overrides=None)`: load template (from embedded bytes per Option C, or `_resource_path` per Option A), select `Startup Report` sheet, write metadata `C3–C11` + `G4`, write valve rows `B–K` from row 15 (≤40, or extension per §7), **never** touch col A or the Cover sheet, **plain values only**, `save(output_path)`.
- **SR-3 — UI entry point.** Add "Export Startup Report…" to the File menu and the job context menu (mirror `_export_job`); reuse `getSaveFileName` + try/except + message box. If a metadata dialog is chosen (§10 decision), show it here.
- **SR-4 — Packaging/build support.** Per the chosen option: embed template bytes (C, no build change) **or** add `--add-data` (A, build change — out of scope this phase) **or** installer-only (E). *No build/updater edits in this audit phase.*
- **SR-5 — Tests.** See §9.
- **SR-6 — Release packaging decision.** Confirm Option C (updater-safe) vs E (installer-only); document in the release notes which clients can receive the feature via auto-update.

---

## 9. Tests required

**Cell/structure assertions** (write to a temp output, reload, assert):
- Metadata `C3–C11` and `G4` hold the expected values; **no cell on the `Cover` sheet is written** (all Cover cells remain formulas); **no `A{r}` is written** (col A formulas untouched).
- Valve rows: `B–K` populated correctly for each record; `A` left to the template formula.
- Pass/Fail: `Pass→PASS`, `Fail→FAIL`, unset→blank cell.
- Optional/missing fields (Site/Building/Floor/Location/Face Velocity/Exec Summary): blank when no data.

**Preservation sanity** (reload output, assert still present — mirrors §3.4):
- DV on `C/E/G`; CF on `G15:G54`; merges incl. `G4:K11`; L–AE hidden+outline; print area `A1:K56`; repeat-header `$14:$14`; legend row.

**Row-count behavior:**
- 0 valves (metadata only, all data rows blank), 1 valve, exactly 40 valves (fills 15–54), 41+ valves (cap-with-warning path **or** extension path if implemented — assert CF/DV/print-area extended and legend relocated).

**Edge / safety:**
- Missing template (embedded-bytes corrupt, or external file absent) → clean error, no half-written output.
- Output created safely (target path locked / open in Excel → `PermissionError` surfaced as a friendly message, not a crash — note `_export_*` currently shows raw `str(exc)`).
- Valve-type values written to `E` are always either a confirmed dropdown value or blank (never an off-list string).

---

## 10. Operator decisions needed

1. **Job-level metadata sourcing.** The report is per-job but the data is per-checkout. Choose:
   (a) derive silently from the records (e.g. first/most-common project, technician, date; `Job.job_number` for ATS #), or
   (b) show a small "Startup Report details" dialog at export time pre-filled from the records, letting the tech confirm/fill Project, Site, Building, Floor, Technician, ATS #, Date, Product Line(s), Executive Summary. **(b) is recommended** because Site/Building/Floor/Exec Summary have no source at all.
2. **Valve Type → `E` mapping** for the 5 ambiguous types: `MAV`, `Snorkel`, `Canopy`, `Draw Down Bench`, `Gas Cabinet` → which of `Supply / General Exhaust / Fume Hood`? (Default if unanswered: leave `E` blank.)
3. **Valve Min/Max CFM source:** header `valve_min_sp`/`valve_max_sp` (recommended) **or** config `valve_min_cfm`/`valve_max_cfm`?
4. **Face Velocity (FPM):** confirm **blank for v1** (no numeric source), or add a numeric field to Checkout later, or (not recommended) parse `face_velocity_notes`.
5. **Template packaging:** Option **C** embed (recommended, updater-safe) vs **E** installer-only vs **A** bundle-as-data (unsafe for exe-only auto-update).
6. **>40 valves:** v1 **cap-at-40 with warning** (recommended) vs implement row-extension now.
7. **ATS Job # / Project source:** `Job.job_number` / `Job.job_name` vs `record.ats_job_number` / `record.project`.
8. **Location/Room (`F`) and Description (`C11`):** blank for v1, or collect in the metadata dialog?

---

## 11. Recommendation

**READY AFTER DECISIONS.**

The technical approach is validated and low-risk (§3.4), the integration point is clear and minimal (§4), and a safe, updater-compatible packaging path exists (§5–§6). No STOP condition is hard-triggered:
- Required source fields *are* identifiable (the missing ones have safe blank/entry defaults).
- Template packaging *need not* break auto-updated installs (Option C/E).
- Pass/Fail mapping is *unambiguous*.
- >40-valves handling is *safe* under the v1 cap.

The only blockers to starting implementation are the **operator decisions in §10** — chiefly the metadata-sourcing model (#1), the 5 ambiguous valve-type mappings (#2), and the packaging choice (#5). Once those are settled, SR-1→SR-3 can proceed surgically without touching the updater, build, installer, or the existing export engine.

---

## Confirmation

- ✅ **No source code changed** (audit + inspection only; analysis scripts ran from a temp dir, not the repo).
- ✅ **No `version.py` change.**
- ✅ **No `build.bat` / `updater.py` / `installer.iss` change** — updater contract untouched.
- ✅ **No release, tag, asset upload, or publish.**
- ✅ **No broad `PROJECT_REVIEW.md` remediation started** — findings used only as guardrails.
- ✅ **Existing export system not rewritten; workbook styling not rebuilt.**

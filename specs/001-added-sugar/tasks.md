# Tasks: Added Sugar Management

**Input**: Design documents from `specs/001-added-sugar/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/added-sugar-api.md`

**Tests**: No separate test tasks are included because the feature specification did not request tests. Use the manual scenarios in `quickstart.md` during implementation validation.

**Organization**: Tasks are grouped by user story. Shared SQLite compatibility changes are foundational because both stories need persisted classification data.

## Phase 1: Setup

**Purpose**: Confirm existing app structure; no new project initialization or dependencies are needed.

- [X] T001 Review the existing ingredient and meal logging paths in `app/main.py` and `static/index.html` against `specs/001-added-sugar/plan.md` before editing.

## Phase 2: Foundational

**Purpose**: Add backward-compatible persistence fields needed by ingredient classification and historical meal summaries.

- [X] T002 Add `counts_as_added_sugar` to the SQLite `ingredients` and `daily_log_items` schemas in `app/main.py`, and extend the existing schema-upgrade path so both fields default to false for existing rows.

**Checkpoint**: Existing SQLite databases start with both new fields available and legacy records treated as unmarked.

## Phase 3: User Story 1 - Classify Ingredient Sugar (Priority: P1) 🎯 MVP

**Goal**: Let users mark and persist whether each ingredient's sugar counts as added sugar.

**Independent Test**: Create and edit an ingredient with the checkbox both selected and unselected; save, reopen, and confirm the setting persists.

### Implementation for User Story 1

- [X] T003 [US1] Add `counts_as_added_sugar` to the ingredient request model and make create/update/list operations in `app/main.py` read, persist, and return the boolean, defaulting omitted values to false.
- [X] T004 [US1] Add a “Count sugar as added” checkbox to the ingredient create/edit interface in `static/index.html`, initialize it from saved ingredient data, and submit its value when creating or updating an ingredient.

**Checkpoint**: Ingredient classifications can be created, changed, persisted, and reviewed independently of daily-limit calculation.

## Phase 4: User Story 2 - Track Daily Added Sugar (Priority: P1)

**Goal**: Compare only sugar from marked ingredients with the selected user's daily sugar limit, while preserving total sugar information.

**Independent Test**: Log marked and unmarked ingredients with known sugar values; confirm daily added-sugar progress counts marked sugar only, total sugar still includes both, and a later ingredient-classification change does not alter the saved log classification.

### Implementation for User Story 2

- [X] T005 [US2] Extend meal log request handling in `app/main.py` to accept each item's added-sugar classification (default false when omitted) and snapshot it into `daily_log_items` when logging or replacing a meal.
- [X] T006 [US2] Preserve `counts_as_added_sugar` when duplicating meal entries in `app/main.py`, without changing total-sugar snapshots.
- [X] T007 [US2] Calculate a distinct `added_sugar` amount from only marked log-item snapshots in the daily summary in `app/main.py`; retain total sugar separately and base sugar remaining/progress on `added_sugar` and the existing target.
- [X] T008 [US2] Include each ingredient's saved `counts_as_added_sugar` value in the frontend meal-log payload and display the daily added-sugar amount against the sugar limit in `static/index.html`, keeping total sugar nutrition distinct.

**Checkpoint**: A day's sugar-limit progress reflects only logged sugar classified as added, scoped to the selected user and date; total sugar remains available.

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Validate persistence and end-to-end behavior against the feature's scenarios.

- [X] T009 [P] Update `README.md` to explain that the daily sugar target measures added sugar and how ingredient classification affects it.
- [X] T010 Follow the manual end-to-end scenarios in `specs/001-added-sugar/quickstart.md` and record any deviations from the specified expected outcomes.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on T001; blocks both user stories.
- **User Story 1 (Phase 3)**: Depends on T002.
- **User Story 2 (Phase 4)**: Depends on T002 and on T003/T004 to create and manage ingredient classifications in the normal UI flow.
- **Polish (Phase 5)**: Run after the relevant stories are implemented; README update T009 can be done in parallel with implementation because it edits a separate file.

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2; no dependency on US2. Delivers the ingredient classification MVP.
- **US2 (P1)**: Starts after Phase 2 and uses the classification managed by US1. Requires US1 integration for the complete user-facing flow.

### Parallel Opportunities

- T009 (`README.md`) can run in parallel with story implementation tasks.
- T005 and T006 both edit `app/main.py` and should be executed sequentially to avoid file conflicts.
- T007 follows T005 because its aggregation depends on stored item snapshots.
- T008 follows T003/T004 and T005/T007 because the UI must submit saved classifications and show the added-sugar summary field.

## Parallel Example: User Story 1

After T002, T003 and T004 concern separate backend and frontend files and may be implemented in parallel:

```text
Task: T003 — Update ingredient model and API persistence in app/main.py
Task: T004 — Add ingredient classification checkbox in static/index.html
```

## Implementation Strategy

### MVP First (User Story 1)

1. Complete T001 and T002.
2. Complete T003 and T004.
3. Validate ingredient classification create/edit persistence independently.

### Incremental Delivery

1. Complete the US1 MVP and confirm the checkbox persists.
2. Complete US2 snapshot, daily aggregation, and progress display.
3. Follow `specs/001-added-sugar/quickstart.md` to verify mixed marked/unmarked ingredients, history stability, duplication, and persistence.

### Simplicity

Keep the implementation in the existing FastAPI module and static page, reuse SQLite schema initialization, and add no service layers, packages, or dependencies.

## Notes

- The user confirmed the end-to-end sugar flow works. After the UI adjustments, frontend JavaScript syntax validation and `git diff --check` passed.

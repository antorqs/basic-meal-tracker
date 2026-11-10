# Implementation Plan: Added Sugar Management

**Branch**: `001-added-sugar` | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-added-sugar/spec.md`

## Summary

Add a per-ingredient “Count sugar as added” classification, preserve the applicable
classification on logged food items, and use only that qualifying sugar for daily sugar-limit
progress. Keep total sugar nutrition intact. Extend the existing FastAPI, SQLite, and static
frontend paths directly, using a small schema extension and backwards-compatible defaults.

## Technical Context

**Language/Version**: Python 3 (existing runtime), HTML, JavaScript

**Primary Dependencies**: FastAPI, Pydantic, SQLite; existing Tailwind CDN and Alpine.js frontend

**Storage**: SQLite, initialized and incrementally extended in `app/main.py`

**Testing**: Existing project has no test suite or test runner configured; manual end-to-end
validation is documented in quickstart. Implementation should add focused automated coverage if
the project adopts a test harness as part of the implementation.

**Target Platform**: Local/Docker-hosted web application

**Project Type**: Single-project web application (Python backend and static frontend)

**Performance Goals**: Added-sugar progress is calculated as part of the existing daily-summary
flow without a separate user-visible wait or additional service.

**Constraints**: Preserve current API flows and total sugar values; persist new fields for
existing SQLite databases; classification is snapshotted for logged entries; no added runtime
dependency or separate service.

**Scale/Scope**: One ingredient classification, one logged-item snapshot value, and one added-
sugar daily total/limit comparison across the existing selected user and date.

## Constitution Check

- **Accurate, Traceable Nutrition**: Pass. Nutrient quantity is still based on logged weight;
  total sugar remains distinct, and classification is snapshotted for history.
- **Clear Personal and Family Boundaries**: Pass. Summary aggregation remains scoped to the
  selected user and date.
- **Simple, Accessible Workflows**: Pass. Add the classification to the existing ingredient
  create/edit interaction and display added-sugar progress in the existing daily summary.
- **Durable and Consistent Data**: Pass. Extend existing SQLite initialization with safe defaults
  and preserve existing records.
- **Verify User-Visible Behavior**: Pass when implementation includes checks for create/edit,
  logging, daily aggregation, and history stability.
- **Architectural Simplicity and No Overengineering**: Pass. Reuse the existing app, storage,
  API, and UI flows; no new layers, services, or dependencies are justified.

## Project Structure

### Documentation (this feature)

```text
specs/001-added-sugar/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── added-sugar-api.md
└── tasks.md
```

### Source Code (repository root)

```text
app/
└── main.py           # SQLite schema, request models, ingredient/logging/summary endpoints
static/
└── index.html        # Existing ingredient management and daily progress UI
```

**Structure Decision**: Keep the established single-project layout. Implement the data and API
changes in the existing FastAPI module and the user controls/summary display in the existing
static page. No additional source modules are needed for this feature.

## Complexity Tracking

No constitution violations. No additional architectural components are proposed.

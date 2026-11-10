<!--
Sync Impact Report
Version change: 1.0.0 → 1.1.0 (added an architectural simplicity principle)
Modified principles: none
Added sections: VI. Architectural Simplicity and No Overengineering
Removed sections: none
Follow-up TODOs: Confirm the original ratification date.
-->
# Simple Meal Tracker Constitution

## Core Principles

### I. Accurate, Traceable Nutrition
Nutrition values and daily totals MUST be derived from explicit ingredient quantities and
documented calculation rules. Saved meal entries MUST preserve a snapshot of the values used
when they were logged so later ingredient or recipe edits do not silently rewrite history.

### II. Clear Personal and Family Boundaries
Every user-specific meal, target, and history operation MUST identify its intended user. Actions
that copy or delete entries MUST be explicit and must not alter another user's data accidentally.

### III. Simple, Accessible Workflows
Core tracking flows MUST work well on mobile screens and keep common actions understandable:
select a date and user, review progress, log food, and correct or duplicate an entry. New
complexity MUST solve a demonstrated user need.

### IV. Durable and Consistent Data
Persistent changes MUST preserve database integrity, including foreign-key relationships and
valid quantities. Schema changes MUST account for existing SQLite data and the application's
Docker persistence model.

### V. Verify User-Visible Behavior
Changes to nutrition calculations, persistence, user/date selection, or meal operations MUST
be checked at the relevant boundary, including integration behavior when multiple components
are involved. Verification results and known gaps MUST be reported with the change.

### VI. Architectural Simplicity and No Overengineering
Because this is a personal project, the architecture MUST remain as simple and direct as
possible. Do not introduce complex design patterns, unnecessary abstraction layers,
microservices, or heavy libraries when the functionality can be implemented simply with the
existing code and structure. Every proposal created through `$speckit-plan` and implementation
performed through `$speckit-implement` MUST justify simplicity as a priority criterion.

## Product and Data Constraints

The product is a personal and family calorie/protein tracker built with FastAPI, SQLite,
Tailwind CSS, and Alpine.js. Changes MUST preserve a usable local and Docker workflow. Nutrition
tracking is informational: the application MUST present recorded estimates as tracking data,
not as medical advice or a diagnosis.

## Development Workflow

Before implementation, identify affected flows and persisted data. For changes to stored data,
consider existing records and migration or compatibility needs. Before completion, review the
affected user-visible behavior and report what was verified; do not claim checks that were not
performed. Keep changes focused and document operational or data-format changes in the README.

## Governance

This constitution governs feature specifications and implementation decisions. Amendments MUST
update this document and its version/date metadata. Use semantic versioning: MAJOR for
incompatible governance changes, MINOR for added or materially expanded principles or rules,
and PATCH for clarifications that do not change obligations. Proposed work MUST be reviewed
against these principles; any conflict MUST be resolved in the specification or explicitly
documented before implementation. Compliance review MUST consider affected principles and
verification evidence.

**Version**: 1.1.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-11-08

# Research: Added Sugar Management

## Decision: Extend the existing ingredient classification and logging flow

Add a boolean added-sugar classification to the ingredient, expose it through the existing
ingredient create/update/list behavior, and capture it on each logged item. Use the captured
value when calculating added-sugar progress.

**Rationale**: The app already creates and updates ingredients through one API model and stores
historical nutrient snapshots on daily log items. Extending those structures keeps behavior
consistent and avoids looking up mutable ingredient data to reinterpret history.

**Alternatives considered**: Derive classification from the current ingredient record each time
a summary is viewed. Rejected because changing an ingredient would silently change prior logged
meals, contrary to the constitution's snapshot principle and the feature's assumption.

## Decision: Default legacy classification to false

Treat existing ingredients with no classification as unmarked. Treat existing daily log items
without a classification snapshot as unmarked.

**Rationale**: This follows the specification's explicit assumption and avoids counting any
existing sugar as added without user classification.

**Alternatives considered**: Infer classification from ingredient name or data source. Rejected
because the repository contains no reliable classification source and inference could overcount.

## Decision: Preserve total sugar separately from added sugar

Keep existing total-sugar nutrition fields and totals intact. Calculate and expose a distinct
added-sugar amount for comparison to the existing daily sugar target.

**Rationale**: The specification requires total sugar to remain available while the limit
measures added sugar. Separation avoids changing general nutrition values to serve a limit.

**Alternatives considered**: Replace total sugar throughout the application with added sugar.
Rejected because it would lose existing nutrition information and change unrelated displays.

## Decision: Use the current app's direct data and UI paths

Keep schema upgrades in existing SQLite initialization, endpoint behavior in `app/main.py`, and
the controls and progress display in `static/index.html`.

**Rationale**: These are the current ownership boundaries in this small application. Reuse is
the simplest implementation and follows the constitution's no-overengineering principle.

**Alternatives considered**: Introduce a service layer, new package, or third-party nutrition
library. Rejected because this feature is a boolean classification and simple aggregation.

## Decision: Extend the existing API contract compatibly

Make the new ingredient input value optional with a false default for older clients, return the
classification in ingredient results, and provide added sugar distinctly in daily-summary
responses. Accept the new logged-item snapshot value with a false default for clients that have
not been updated.

**Rationale**: Existing local clients and persisted data remain usable while the UI adopts the
new field. Exact response naming and summary aggregation are described in the API contract.

**Alternatives considered**: Require an API version change. Rejected because optional input and
additive response fields are sufficient for this single-user-facing application.

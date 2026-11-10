# Feature Specification: Added Sugar Management

**Feature Branch**: `001-added-sugar`

**Created**: 2026-11-09

**Status**: Draft

**Input**: User description: "Feature: Improvement in sugar management. Sugar handling is not correct in the system. In this new iteration we will improve it with the following changes: Every ingredient will have a check 'count sugar as added'; daily sugar limit is 'added sugar'; For the daily sugar limit only sum the sugar of ingredients with the check marked"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Classify Ingredient Sugar (Priority: P1)

As a user managing ingredient nutrition data, I can mark whether an ingredient's sugar counts as added sugar, so that the daily limit reflects the intended kind of sugar.

**Why this priority**: Ingredient classification is the source of truth for calculating added sugar.

**Independent Test**: Create or edit an ingredient, set its added-sugar option, save it, and reopen it to confirm the setting is retained.

**Acceptance Scenarios**:

1. **Given** an ingredient being created or edited, **When** the user marks “Count sugar as added” and saves, **Then** the ingredient is classified as counting toward added sugar.
2. **Given** an ingredient being created or edited, **When** the user leaves “Count sugar as added” unmarked and saves, **Then** its sugar does not count toward the added-sugar total.
3. **Given** a saved ingredient, **When** the user opens it for editing, **Then** the displayed option matches its saved classification.

---

### User Story 2 - Track Daily Added Sugar (Priority: P1)

As a user reviewing a day's nutrition, I can compare only the sugar from ingredients classified as added sugar against my daily sugar limit.

**Why this priority**: This corrects the central daily sugar tracking behavior and makes the limit meaningful.

**Independent Test**: Log items containing both marked and unmarked ingredients and confirm the daily sugar amount and remaining amount include only marked ingredients' sugar.

**Acceptance Scenarios**:

1. **Given** a day with marked and unmarked ingredients containing sugar, **When** the user views daily progress, **Then** the sugar amount used against the daily limit is the sum for marked ingredients only.
2. **Given** a day containing only unmarked ingredients with sugar, **When** the user views daily progress, **Then** the amount used against the added-sugar limit is zero.
3. **Given** a day containing a marked ingredient with zero sugar, **When** the user views daily progress, **Then** it contributes zero to the amount used.

### Edge Cases

- An ingredient with no added-sugar classification must be treated as not counting toward added sugar.
- Changing the classification of an ingredient must have a clearly consistent effect on existing logged meals; this specification assumes each log preserves the classification used when it was recorded, consistent with the project's historical snapshot principle.
- The regular sugar nutrient value remains available as nutrition information; only the value compared with the daily sugar limit is restricted to marked ingredients.
- Repeated use of the same ingredient across multiple meal entries contributes its marked sugar once per logged quantity.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a user set and change a “Count sugar as added” classification for every ingredient.
- **FR-002**: The system MUST retain each ingredient's classification when the ingredient is saved and show it when the ingredient is edited.
- **FR-003**: The daily sugar limit MUST represent added sugar.
- **FR-004**: The sugar amount compared with the daily limit MUST include sugar only from ingredients marked “Count sugar as added.”
- **FR-005**: Sugar from unmarked ingredients MUST NOT increase the daily amount used or reduce the remaining amount for the daily sugar limit.
- **FR-006**: The daily added-sugar amount MUST account for the logged quantity of each ingredient and combine qualifying sugar across the selected user's meals for the selected date.
- **FR-007**: The system MUST preserve total sugar as a nutrition value separately from the added-sugar amount used for the limit.
- **FR-008**: The classification used for an already logged meal MUST remain stable if the ingredient's classification is later changed.

### Key Entities *(include if feature involves data)*

- **Ingredient**: A food item with nutrition values and a classification indicating whether its sugar counts as added sugar.
- **Daily meal entry**: A dated, user-associated record of ingredient quantities and nutrition values, including the added-sugar classification relevant when logged.
- **Daily sugar limit**: The user's configured limit for added sugar, compared against qualifying sugar consumed on a date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all checked daily summaries, the amount compared with the sugar limit equals the sum of sugar from marked ingredients in that day's logged quantities.
- **SC-002**: In all checked daily summaries, sugar from unmarked ingredients contributes zero to the amount used against the limit.
- **SC-003**: Users can set or change an ingredient's classification and see the saved value on reopening the ingredient in one complete create or edit flow.
- **SC-004**: The displayed total sugar nutrition value remains available and distinct from the added-sugar amount compared with the daily limit.

## Assumptions

- The existing daily sugar target is retained as the user's added-sugar limit; only the meaning of the consumption amount compared against it changes.
- Existing ingredients without a saved classification are treated as unmarked until the user classifies them.
- Historical meal entries retain the classification in effect when they were logged, consistent with the constitution's snapshot requirement. Previously recorded entries without that snapshot are treated as unmarked unless a later migration policy specifies otherwise.
- The ingredient create/edit flow is the place where users manage the classification.

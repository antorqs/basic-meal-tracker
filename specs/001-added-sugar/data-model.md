# Data Model: Added Sugar Management

## Ingredient

Represents a named food and its nutrition values per 100 g.

| Field | Type | Rules |
|---|---|---|
| `counts_as_added_sugar` | Boolean | Defaults to false for new and legacy ingredients; editable and returned by ingredient operations. |

Existing ingredient identity and nutrition fields remain unchanged.

## Daily log item

Represents one ingredient and quantity recorded in a user's dated meal, with a snapshot of
nutrition values.

| Field | Type | Rules |
|---|---|---|
| `counts_as_added_sugar` | Boolean | Snapshot of the ingredient classification when this item is logged; defaults to false for existing rows. |
| `sugar` | Number | Total sugar for the logged quantity; remains the total-sugar nutrition value. |

For an item whose snapshot is true, its `sugar` contributes to added sugar; otherwise it
contributes zero. Copying an entry to another user copies this snapshot. Editing/replacing a
logged meal refreshes the snapshot from the submitted ingredient data/current classification.

## Daily summary

Existing total sugar remains the sum of all item's `sugar`. Added sugar is the sum of `sugar`
for only items whose `counts_as_added_sugar` snapshot is true, grouped by selected user and date.
The existing daily sugar target is interpreted as the added-sugar limit. Remaining sugar
progress is target minus added sugar, using the application's current presentation conventions.

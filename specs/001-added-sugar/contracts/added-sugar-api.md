# Added Sugar API Contract

The feature extends existing endpoints. Existing routes and unrelated fields remain unchanged.

## Ingredient operations

Affected routes: `GET /api/ingredients`, `POST /api/ingredients`, and
`PUT /api/ingredients/{ingredient_id}`.

- Ingredient request and response objects include `counts_as_added_sugar` as a boolean.
- For backward compatibility, omitted input is interpreted as `false`.
- Ingredient list responses return the persisted value.
- Updating an ingredient changes its current classification; it does not rewrite snapshots on
  previously logged items.

## Meal logging and editing

Affected routes: `POST /api/logs` and `PUT /api/logs/{log_id}`.

- Each submitted log item includes `counts_as_added_sugar` as a boolean, defaulting to `false`
  when omitted.
- The server stores the value with the item's nutrition snapshot.
- Existing total sugar calculation and log response behavior remain available.

## Daily summary

Affected route: `GET /api/daily`.

- Existing total sugar remains available as total sugar.
- The response exposes a distinct `added_sugar` consumed amount, calculated from log-item sugar
  snapshots marked true and scoped to the requested user and date.
- Existing `target_sugar` is the added-sugar limit; remaining sugar progress is based on
  `added_sugar` and `target_sugar`, not total sugar.

Exact response envelope follows the current endpoint's conventions; the new field is additive.

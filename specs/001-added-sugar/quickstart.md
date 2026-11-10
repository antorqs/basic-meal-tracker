# Quickstart: Added Sugar Validation

## Prerequisites

- Python environment and dependencies from `requirements.txt`, or Docker Compose.
- A browser opened to the running application.

## Start the application

Choose one:

```bash
docker compose up --build
```

Or follow the local setup in the repository README, then run:

```bash
uvicorn app.main:app --reload
```

## Validation scenarios

1. Create an ingredient with nonzero sugar, mark “Count sugar as added,” save it, and confirm
   the classification is still selected when editing it again.
2. Create another ingredient with nonzero sugar and leave the option unmarked.
3. Log a meal containing a known quantity of each ingredient. Confirm daily sugar-limit progress
   increases by the marked ingredient's sugar for that quantity only.
4. Confirm the total-sugar nutrition display includes sugar from both ingredients, while the
   daily sugar-limit progress does not include the unmarked ingredient.
5. Change the first ingredient's classification and confirm the already logged meal keeps the
   classification snapshot from when it was recorded.
6. Duplicate the logged meal to the other user and confirm its added-sugar snapshot and the two
   users' daily totals remain correctly scoped.
7. Restart the application against the same SQLite data and confirm ingredient classifications
   and daily progress persist.

## Expected outcome

The amount compared with the daily sugar target equals the sum of logged sugar from items marked
as added sugar when recorded. Total sugar continues to include all logged items.

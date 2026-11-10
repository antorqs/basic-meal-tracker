import os
import tempfile
import unittest
from pathlib import Path


_test_db_dir = tempfile.TemporaryDirectory(prefix="meal-tracker-reports-")
os.environ["MEAL_TRACKER_DB"] = str(Path(_test_db_dir.name) / "reports.db")

from fastapi import HTTPException

from app import main as tracker


class ReportsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="meal-tracker-report-case-")
        tracker.DB_PATH = Path(self.temp_dir.name) / "reports.db"
        tracker.init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_target(self, effective_date, calories=2000, protein=100, carbs=200, sugar=30, fat=70):
        with tracker.connect() as db:
            db.execute(
                "INSERT INTO user_targets(user_id,effective_date,target_calories,target_protein,"
                "target_carbs,target_sugar,target_fat) VALUES (1,?,?,?,?,?,?) "
                "ON CONFLICT(user_id,effective_date) DO UPDATE SET target_calories=excluded.target_calories,"
                "target_protein=excluded.target_protein,target_carbs=excluded.target_carbs,"
                "target_sugar=excluded.target_sugar,target_fat=excluded.target_fat",
                (effective_date, calories, protein, carbs, sugar, fat),
            )

    def add_log(self, day, meal, items, user_id=1):
        totals = {
            key: sum(item.get(key, 0) for item in items)
            for key in ("calories", "protein", "carbs", "sugar", "fat")
        }
        with tracker.connect() as db:
            cur = db.execute(
                "INSERT INTO daily_logs(user_id,date,meal_type,total_calories,total_protein,"
                "total_carbs,total_sugar,total_fat) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, day, meal, *(totals[key] for key in ("calories", "protein", "carbs", "sugar", "fat"))),
            )
            db.executemany(
                "INSERT INTO daily_log_items(daily_log_id,ingredient_name,weight,calories,protein,"
                "carbs,sugar,fat,counts_as_added_sugar) VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (
                        cur.lastrowid,
                        item["name"],
                        item.get("weight", 0),
                        item.get("calories", 0),
                        item.get("protein", 0),
                        item.get("carbs", 0),
                        item.get("sugar", 0),
                        item.get("fat", 0),
                        int(item.get("counts_as_added_sugar", False)),
                    )
                    for item in items
                ],
            )

    def test_weekly_windows_use_monday_and_rolling_seven_day_ranges(self):
        self.add_target("2026-11-01", calories=2000)
        self.add_target("2026-11-10", calories=2200)
        self.add_log("2026-11-05", "Breakfast", [{"name": "Oats", "calories": 500}])
        self.add_log("2026-11-11", "Lunch", [{"name": "Rice", "calories": 1000}])

        result = tracker.weekly_report(user_id=1, as_of="2026-11-11")
        rolling = result["last_7_days"]
        current = result["current_week"]

        self.assertEqual((rolling["start_date"], rolling["end_date"]), ("2026-11-05", "2026-11-11"))
        self.assertEqual((current["start_date"], current["end_date"]), ("2026-11-09", "2026-11-11"))
        self.assertEqual(rolling["averages"]["logged_days"], 2)
        self.assertEqual(rolling["averages"]["values"]["calories"], 750)
        self.assertEqual(rolling["averages"]["goals"]["calories"], 2100)
        self.assertEqual(current["days"][0]["values"]["calories"], 0)
        self.assertEqual(current["averages"]["logged_days"], 1)

    def test_sunday_current_week_starts_on_monday(self):
        result = tracker.weekly_report(user_id=1, as_of="2026-11-15")
        self.assertEqual(result["last_7_days"]["start_date"], "2026-11-09")
        self.assertEqual(result["current_week"]["start_date"], "2026-11-09")
        self.assertEqual(len(result["current_week"]["days"]), 7)
        self.assertIsNone(result["current_week"]["averages"]["values"]["calories"])

    def test_zero_goal_has_no_percent_comparison_and_keeps_actual_value(self):
        self.add_target("2026-11-01", carbs=0)
        self.add_log("2026-11-10", "Lunch", [{"name": "Rice", "carbs": 35}])
        day = tracker.weekly_report(user_id=1, as_of="2026-11-10")["last_7_days"]["days"][6]
        self.assertEqual(day["values"]["carbs"], 35)
        self.assertEqual(day["goals"]["carbs"], 0)
        self.assertIsNone(day["progress_percent"]["carbs"])

    def test_contributors_aggregate_ingredient_across_meals_and_added_sugar_only(self):
        self.add_log(
            "2026-11-10",
            "Breakfast",
            [
                {"name": "Milk", "weight": 100, "protein": 4, "sugar": 5},
                {"name": "Oats", "weight": 50, "carbs": 10, "protein": 3, "sugar": 2, "counts_as_added_sugar": True},
            ],
        )
        self.add_log(
            "2026-11-10",
            "Dinner",
            [
                {"name": "Milk", "weight": 150, "protein": 6, "sugar": 7},
                {"name": "Oats", "weight": 50, "carbs": 15, "protein": 2, "sugar": 4, "counts_as_added_sugar": True},
                {"name": "Honey", "weight": 10, "carbs": 8, "sugar": 8},
            ],
        )

        day = tracker.weekly_report(user_id=1, as_of="2026-11-10")["last_7_days"]["days"][6]
        protein_leader = day["leaders"]["protein"][0]
        carbs_leader = day["leaders"]["carbs"][0]
        sugar_leader = day["leaders"]["added_sugar"][0]

        self.assertEqual((protein_leader["ingredient"], protein_leader["grams"], protein_leader["value"]), ("Milk", 250, 10))
        self.assertEqual(protein_leader["meals"], ["Breakfast", "Dinner"])
        self.assertEqual((carbs_leader["ingredient"], carbs_leader["value"]), ("Oats", 25))
        self.assertEqual((sugar_leader["ingredient"], sugar_leader["value"]), ("Oats", 6))

    def test_foods_report_is_inclusive_and_keeps_total_sugar_and_added_flag(self):
        self.add_log("2026-11-09", "Lunch", [{"name": "Honey, raw", "weight": 20, "sugar": 12, "counts_as_added_sugar": True}])
        self.add_log("2026-11-10", "Dinner", [{"name": "Apple", "weight": 150, "sugar": 15}], user_id=2)
        result = tracker.foods_report(user_id=1, from_date="2026-11-09", to_date="2026-11-09")

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["ingredient_name"], "Honey, raw")
        self.assertEqual(result["items"][0]["sugar"], 12)
        self.assertTrue(result["items"][0]["counts_as_added_sugar"])

    def test_invalid_range_and_unknown_user_return_http_errors(self):
        with self.assertRaises(HTTPException) as invalid_range:
            tracker.foods_report(user_id=1, from_date="2026-11-11", to_date="2026-11-10")
        self.assertEqual(invalid_range.exception.status_code, 400)
        with self.assertRaises(HTTPException) as unknown_user:
            tracker.weekly_report(user_id=999, as_of="2026-11-11")
        self.assertEqual(unknown_user.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Import per-100g nutrition values from the project CSV into the meal-tracker API.

Preview changes first with:
    python scripts/import_nutrition_csv.py

Apply them with:
    python scripts/import_nutrition_csv.py --apply
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://192.168.68.60:8001"
DEFAULT_CSV = Path(__file__).resolve().parents[1] / "data" / "informacion_nutricional.csv"
REQUIRED_COLUMNS = (
    "Producto",
    "Calorias_kcal",
    "Proteinas_g",
    "Carbohidratos_g",
    "Azucares_g",
    "Grasas_g",
)
API_FIELDS = (
    ("Calorias_kcal", "calories_per_100g"),
    ("Proteinas_g", "protein_per_100g"),
    ("Carbohidratos_g", "carbs_per_100g"),
    ("Azucares_g", "sugar_per_100g"),
    ("Grasas_g", "fat_per_100g"),
)


class ImportErrorDetail(Exception):
    """Expected validation or API failure suitable for a concise CLI message."""


def normalized_name(name):
    return name.strip().casefold()


def parse_value(raw, row_number, column):
    value = raw.strip()
    if not value:
        raise ImportErrorDetail(f"CSV row {row_number}: {column} is empty")
    try:
        number = float(value.replace(",", "."))
    except ValueError as exc:
        raise ImportErrorDetail(
            f"CSV row {row_number}: {column} is not a valid number: {raw!r}"
        ) from exc
    if not math.isfinite(number) or number < 0:
        raise ImportErrorDetail(
            f"CSV row {row_number}: {column} must be a finite, nonnegative number"
        )
    return number


def read_csv(csv_path):
    try:
        stream = csv_path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ImportErrorDetail(f"Cannot open CSV file {csv_path}: {exc}") from exc

    with stream:
        sample = stream.read(8192)
        stream.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(stream, dialect=dialect)
        headers = reader.fieldnames or []
        missing = [column for column in REQUIRED_COLUMNS if column not in headers]
        if missing:
            raise ImportErrorDetail(
                "CSV is missing required column(s): " + ", ".join(missing)
            )

        products = []
        seen = set()
        for row_number, row in enumerate(reader, start=2):
            product = (row.get("Producto") or "").strip()
            if not product:
                raise ImportErrorDetail(f"CSV row {row_number}: Producto is empty")
            key = normalized_name(product)
            if key in seen:
                raise ImportErrorDetail(
                    f"CSV row {row_number}: duplicate Producto after trimming/case-folding: {product!r}"
                )
            seen.add(key)
            payload = {"name": product}
            for csv_column, api_field in API_FIELDS:
                payload[api_field] = parse_value(
                    row.get(csv_column) or "", row_number, csv_column
                )
            products.append({"name": product, "payload": payload})

    if not products:
        raise ImportErrorDetail("CSV contains no ingredient rows")
    return products


def request_json(url, method="GET", payload=None, timeout=15):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise ImportErrorDetail(
            f"{method} {url} returned HTTP {exc.code}"
            + (f": {detail}" if detail else "")
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ImportErrorDetail(f"Could not reach {url}: {exc}") from exc

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ImportErrorDetail(f"{method} {url} returned invalid JSON") from exc


def match_products(products, ingredients):
    by_name = {}
    for ingredient in ingredients:
        key = normalized_name(ingredient.get("name", ""))
        if key:
            by_name.setdefault(key, []).append(ingredient)

    matches = []
    errors = []
    matched_ids = set()
    for product in products:
        key = normalized_name(product["name"])
        candidates = by_name.get(key, [])
        if len(candidates) != 1:
            reason = "not found" if not candidates else "ambiguous database name"
            errors.append(f"{product['name']!r}: {reason}")
            continue
        ingredient = candidates[0]
        if ingredient["id"] in matched_ids:
            errors.append(f"{product['name']!r}: database ingredient matched more than once")
            continue
        matched_ids.add(ingredient["id"])
        payload = product["payload"].copy()
        # Keep the canonical database spelling; only nutrition values are changed.
        payload["name"] = ingredient["name"]
        matches.append((product["name"], ingredient, payload))

    if errors:
        details = "\n  - ".join(errors)
        raise ImportErrorDetail(
            f"Preflight failed for {len(errors)} CSV product(s); no updates were sent:\n  - {details}"
        )
    return matches


def display_value(value):
    return f"{value:g}"


def run():
    parser = argparse.ArgumentParser(
        description="Update ingredient calories, protein, carbs, sugar, and fat from CSV."
    )
    parser.add_argument(
        "--csv", type=Path, default=DEFAULT_CSV, help="CSV path (default: project data file)"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Meal-tracker URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="send updates; without this flag the script only previews changes",
    )
    parser.add_argument("--timeout", type=float, default=15, help="HTTP timeout in seconds")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    try:
        products = read_csv(args.csv)
        ingredients = request_json(f"{base_url}/api/ingredients", timeout=args.timeout)
        if not isinstance(ingredients, list):
            raise ImportErrorDetail("GET /api/ingredients did not return a JSON list")
        matches = match_products(products, ingredients)

        mode = "APPLY" if args.apply else "DRY RUN"
        print(f"{mode}: {len(matches)} ingredient update(s) from {args.csv}")
        for csv_name, ingredient, payload in matches:
            old = ", ".join(
                f"{key.removesuffix('_per_100g')}={display_value(ingredient.get(key, 0))}"
                for _, key in API_FIELDS
            )
            new = ", ".join(
                f"{key.removesuffix('_per_100g')}={display_value(payload[key])}"
                for _, key in API_FIELDS
            )
            print(f"  {csv_name}: {old} -> {new}")

        if not args.apply:
            print("No changes sent. Rerun with --apply to update the deployed database.")
            return 0

        failures = []
        successes = 0
        for csv_name, ingredient, payload in matches:
            url = f"{base_url}/api/ingredients/{quote(str(ingredient['id']), safe='')}"
            try:
                request_json(url, method="PUT", payload=payload, timeout=args.timeout)
                successes += 1
                print(f"UPDATED: {csv_name}")
            except ImportErrorDetail as exc:
                failures.append((csv_name, str(exc)))
                print(f"FAILED: {csv_name}: {exc}", file=sys.stderr)

        print(f"Finished: {successes} updated, {len(failures)} failed.")
        if failures:
            print("Rerun after resolving failures; already-updated rows are safe to repeat.")
            return 1
        return 0
    except ImportErrorDetail as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())

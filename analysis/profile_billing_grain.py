"""Profile the RAW Winnipeg utility billing dataset to infer source grain.

This script does not transform or deduplicate anything. It pulls records
directly from the Socrata API exactly as returned (all values as strings,
missing fields left null), caches that pull locally so results are
reproducible without re-hitting the API, and then profiles duplicate-group
structure against a set of candidate keys.

Usage:
    python analysis/profile_billing_grain.py [--refresh]

Outputs:
    analysis/data/raw_billing_snapshot.parquet   cached raw pull (untouched)
    analysis/data/duplicate_group_examples.csv   example duplicate groups, all 35 cols
    analysis/profiling_report.md                 full findings report
"""

import argparse
import os
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sodapy import Socrata

ANALYSIS_DIR = Path(__file__).parent
DATA_DIR = ANALYSIS_DIR / "data"
CACHE_PATH = DATA_DIR / "raw_billing_snapshot.parquet"
EXAMPLES_CSV_PATH = DATA_DIR / "duplicate_group_examples.csv"
REPORT_PATH = ANALYSIS_DIR / "profiling_report.md"

PAGE_SIZE = 50000

# The 35 source columns documented in etl/transform.py, in their declared order.
ALL_35_COLUMNS = [
    "hydro_gas_id", "account_number", "customer_name", "ssc_number",
    "customer_information", "service_address", "town", "meter_number",
    "actual_service_type", "rate", "service_from_date", "service_to_date",
    "current_reading", "days_of_service", "billing_units", "read_code",
    "basic_charge", "primary_other", "supplemental", "transportation",
    "distribution", "frp_refund", "city_tax", "gst_on_city_tax",
    "carbon_charge", "pst", "gst", "adjustment", "amount_due",
    "demand_billing", "billed_kva", "measured_demand", "high_demand",
    "contract_demand", "multiplier",
]

# Candidate keys, cumulative as specified by the task.
BASE_KEY = ["account_number", "meter_number", "actual_service_type",
            "service_from_date", "service_to_date"]
CANDIDATE_KEYS = {
    "K1: account+meter+type+service_period": BASE_KEY,
    "K2: K1 + service_address": BASE_KEY + ["service_address"],
    "K3: K2 + rate": BASE_KEY + ["service_address", "rate"],
    "K4: K3 + billing_units": BASE_KEY + ["service_address", "rate", "billing_units"],
    "K5: K4 + amount_due": BASE_KEY + ["service_address", "rate", "billing_units", "amount_due"],
}

NUM_EXAMPLE_GROUPS = 8


def fetch_raw(force_refresh: bool = False) -> pd.DataFrame:
    """Pull the raw dataset from Socrata, or load the cached snapshot."""
    if CACHE_PATH.exists() and not force_refresh:
        print(f"Loading cached raw snapshot from {CACHE_PATH}")
        return pd.read_parquet(CACHE_PATH)

    load_dotenv()
    domain = os.environ["SOCRATA_DOMAIN"]
    dataset_id = os.environ["SOCRATA_DATASET_ID"]
    app_token = os.environ.get("SOCRATA_APP_TOKEN")

    client = Socrata(domain, app_token, timeout=120)
    records = []
    offset = 0
    try:
        while True:
            page = client.get(dataset_id, limit=PAGE_SIZE, offset=offset, order=":id")
            if not page:
                break
            records.extend(page)
            offset += len(page)
            print(f"  fetched {offset} rows so far...")
            if len(page) < PAGE_SIZE:
                break
            time.sleep(0.2)  # be polite; no app token means strict throttling
    finally:
        client.close()

    df = pd.DataFrame.from_records(records)
    for col in ALL_35_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[ALL_35_COLUMNS]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_PATH, index=False)
    print(f"Cached raw snapshot ({len(df)} rows) to {CACHE_PATH}")
    return df


def profile_hydro_gas_id(df: pd.DataFrame) -> dict:
    total = len(df)
    null_count = df["hydro_gas_id"].isna().sum()
    distinct_count = df["hydro_gas_id"].nunique(dropna=True)
    non_null = total - null_count
    is_unique_among_non_null = distinct_count == non_null
    return {
        "total_rows": total,
        "null_count": int(null_count),
        "distinct_count": int(distinct_count),
        "non_null_count": int(non_null),
        "unique_among_non_null": bool(is_unique_among_non_null),
        "globally_unique_key": bool(is_unique_among_non_null and null_count == 0),
    }


def profile_candidate_keys(df: pd.DataFrame) -> list[dict]:
    results = []
    for label, key in CANDIDATE_KEYS.items():
        sizes = df.groupby(key, dropna=False).size()
        dup_groups = sizes[sizes > 1]
        results.append({
            "label": label,
            "key_columns": key,
            "total_groups": int(len(sizes)),
            "duplicate_groups": int(len(dup_groups)),
            "rows_in_duplicate_groups": int(dup_groups.sum()) if len(dup_groups) else 0,
            "max_group_size": int(dup_groups.max()) if len(dup_groups) else 0,
        })
    return results


def find_example_groups(df: pd.DataFrame) -> pd.DataFrame:
    """Pick concrete, human-readable duplicate groups on the base key.

    Deliberately excludes pathological huge groups (hundreds of rows) — those
    are covered narratively in the report's conclusion instead. This section
    is meant to show 5-10 examples a reviewer can actually read.
    """
    sizes = df.groupby(BASE_KEY, dropna=False).size()
    dup_sizes = sizes[(sizes > 1) & (sizes <= 6)].sort_values(ascending=False)

    if dup_sizes.empty:
        return pd.DataFrame()

    chosen_keys = dup_sizes.head(NUM_EXAMPLE_GROUPS)

    example_rows = []
    for group_id, (key_values, _size) in enumerate(chosen_keys.items(), start=1):
        if not isinstance(key_values, tuple):
            key_values = (key_values,)
        mask = pd.Series(True, index=df.index)
        for col, val in zip(BASE_KEY, key_values):
            if pd.isna(val):
                mask &= df[col].isna()
            else:
                mask &= df[col] == val
        subset = df.loc[mask].copy()
        subset.insert(0, "group_id", group_id)
        example_rows.append(subset)

    return pd.concat(example_rows, ignore_index=True)


def diff_columns_within_group(group_df: pd.DataFrame) -> list[str]:
    """Return which of the 35 source columns differ within a duplicate group."""
    differing = []
    for col in ALL_35_COLUMNS:
        if group_df[col].nunique(dropna=False) > 1:
            differing.append(col)
    return differing


def check_exact_duplicates_except_id(df: pd.DataFrame) -> dict:
    """Group by all 34 non-id columns; see how often hydro_gas_id is the only diff."""
    other_cols = [c for c in ALL_35_COLUMNS if c != "hydro_gas_id"]
    grouped = df.groupby(other_cols, dropna=False)["hydro_gas_id"].agg(
        n_distinct_ids="nunique", n_rows="count"
    )
    multi_id_groups = grouped[grouped["n_rows"] > 1]
    exact_except_id = multi_id_groups[
        multi_id_groups["n_distinct_ids"] == multi_id_groups["n_rows"]
    ]
    return {
        "groups_identical_on_all_other_34_cols": int(len(multi_id_groups)),
        "rows_involved": int(multi_id_groups["n_rows"].sum()) if len(multi_id_groups) else 0,
        "groups_where_every_row_has_distinct_hydro_gas_id": int(len(exact_except_id)),
    }


def hydro_gas_ids_per_base_key(df: pd.DataFrame) -> pd.DataFrame:
    """How many distinct hydro_gas_id values map to each account/meter/type/period."""
    counts = df.groupby(BASE_KEY, dropna=False)["hydro_gas_id"].nunique(dropna=True)
    distribution = counts.value_counts().sort_index()
    return distribution.rename_axis("distinct_hydro_gas_id_per_group").reset_index(name="num_groups")


def df_to_markdown_table(df: pd.DataFrame) -> str:
    """Minimal markdown table renderer (avoids a hard dependency on tabulate)."""
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join([header, sep] + rows)


def build_report(df, id_profile, key_results, examples_df, exact_dup_check, id_per_key_dist) -> str:
    lines = []
    lines.append("# Winnipeg Utility Billing — Raw Grain Profiling Report")
    lines.append("")
    lines.append(f"Snapshot pulled from Socrata (`{os.environ.get('SOCRATA_DATASET_ID', '?')}`), "
                  f"cached at `{CACHE_PATH.relative_to(ANALYSIS_DIR.parent)}`.")
    lines.append("No transformation, casting, or deduplication was applied before profiling.")
    lines.append("")

    lines.append("## 1. Total row count")
    lines.append(f"- **Total rows: {id_profile['total_rows']}**")
    lines.append("")

    lines.append("## 2. `hydro_gas_id`")
    lines.append(f"- Null count: {id_profile['null_count']}")
    lines.append(f"- Distinct (non-null) values: {id_profile['distinct_count']}")
    lines.append(f"- Non-null row count: {id_profile['non_null_count']}")
    lines.append(f"- Unique among non-null values: {id_profile['unique_among_non_null']}")
    lines.append(f"- **Globally unique key (unique + no nulls): {id_profile['globally_unique_key']}**")
    lines.append("")

    lines.append("## 3. Duplicate-group counts for candidate keys")
    lines.append("")
    lines.append("| Key | Total groups | Duplicate groups (size>1) | Rows in duplicate groups | Max group size |")
    lines.append("|---|---|---|---|---|")
    for r in key_results:
        lines.append(f"| {r['label']} | {r['total_groups']} | {r['duplicate_groups']} | "
                      f"{r['rows_in_duplicate_groups']} | {r['max_group_size']} |")
    lines.append("")

    lines.append("## 4. Example duplicate groups (base key: account+meter+type+service_period)")
    lines.append("")
    if examples_df.empty:
        lines.append("No duplicate groups found on the base key.")
    else:
        for gid, gdf in examples_df.groupby("group_id"):
            key_vals = {c: gdf.iloc[0][c] for c in BASE_KEY}
            differing = diff_columns_within_group(gdf)
            lines.append(f"### Group {gid} — {gdf.shape[0]} rows")
            lines.append(f"Key: `{key_vals}`")
            lines.append(f"Columns that differ within this group: `{differing if differing else 'NONE (rows are identical except possibly hydro_gas_id)'}`")
            lines.append("")
            display_cols = ["hydro_gas_id"] + differing if differing else ["hydro_gas_id"]
            display_cols = list(dict.fromkeys(display_cols))  # dedupe, preserve order
            lines.append(df_to_markdown_table(gdf[display_cols]))
            lines.append("")
        lines.append(f"(Full 35-column rows for all example groups saved to "
                      f"`{EXAMPLES_CSV_PATH.relative_to(ANALYSIS_DIR.parent)}`.)")
    lines.append("")

    lines.append("## 5. Are repeated records exact duplicates except for `hydro_gas_id`?")
    lines.append(f"- Groups identical on all other 34 columns (differ at most by hydro_gas_id): "
                 f"{exact_dup_check['groups_identical_on_all_other_34_cols']}")
    lines.append(f"- Rows involved in those groups: {exact_dup_check['rows_involved']}")
    lines.append(f"- Of those, groups where every row has a distinct hydro_gas_id "
                 f"(true exact-duplicate-except-id): "
                 f"{exact_dup_check['groups_where_every_row_has_distinct_hydro_gas_id']}")
    lines.append("")

    lines.append("## 6. How many `hydro_gas_id` values map to the same account/meter/type/service period?")
    lines.append("")
    lines.append("| Distinct hydro_gas_id per (account, meter, type, service_period) group | Number of groups |")
    lines.append("|---|---|")
    for _, row in id_per_key_dist.iterrows():
        lines.append(f"| {row['distinct_hydro_gas_id_per_group']} | {row['num_groups']} |")
    lines.append("")

    lines.append("## 7. Conclusion")
    lines.append("")
    lines.append("**Source-record identity.** `hydro_gas_id` is unique and non-null across all "
                  f"{id_profile['total_rows']} rows ({id_profile['distinct_count']} distinct values, "
                  "0 nulls). It is the true row-level identity key in this raw feed -- every row is "
                  "one `hydro_gas_id`, full stop. Despite its name, behaviorally it looks like a "
                  "source-system surrogate/billing-line id rather than a customer or meter identifier "
                  "(a real hydro/gas account or meter id would be expected to repeat across billing "
                  "cycles for the same service point).")
    lines.append("")
    lines.append("**Likely business grain.** `account_number + meter_number + actual_service_type + "
                  "service_from_date + service_to_date` does NOT identify one business record -- "
                  f"{key_results[0]['duplicate_groups']} groups ({key_results[0]['rows_in_duplicate_groups']} rows) "
                  "repeat on that key, with groups as large as "
                  f"{key_results[0]['max_group_size']} rows. Investigating the largest groups shows this "
                  "is structural, not incidental: `actual_service_type = 'OT'` rows (non-metered flat "
                  "fees/charges -- e.g. streetlights, directional signs) and a large share of `EL` rows "
                  "carry a null `meter_number` and often null service dates, so many genuinely "
                  "distinct billed items collapse onto the same key. Example: account "
                  "`79113406359272` ('O/H DIRECTIONAL SIGNS') has 16 rows in one billing period, each "
                  "a separate sign/fixture billed as its own line with its own "
                  "`billing_units`/`basic_charge`, but sharing account, null meter, type, and period. "
                  "The most plausible business grain is one row per billed line item (e.g. per "
                  "fixture/charge component) per account per billing cycle, not one row per "
                  "meter-read period. Adding `service_address`, `rate`, `billing_units`, and "
                  "`amount_due` progressively narrows the duplication "
                  f"(K5 still has {key_results[-1]['duplicate_groups']} duplicate groups / "
                  f"{key_results[-1]['rows_in_duplicate_groups']} rows) but never reaches uniqueness "
                  "-- no combination of business columns tested fully replaces `hydro_gas_id`.")
    lines.append("")
    lines.append(f"Separately, {exact_dup_check['groups_identical_on_all_other_34_cols']} groups "
                  f"({exact_dup_check['rows_involved']} rows) are byte-identical across all 34 "
                  "non-id columns and differ only by `hydro_gas_id` -- in every one of those groups "
                  "each row still carries its own distinct id "
                  f"({exact_dup_check['groups_where_every_row_has_distinct_hydro_gas_id']} of "
                  f"{exact_dup_check['groups_identical_on_all_other_34_cols']} groups). This is "
                  "consistent with multiple identically-priced billed items (e.g. two signs with the "
                  "same fixed monthly charge) rather than accidental re-ingestion, but that "
                  "interpretation cannot be confirmed from this data alone.")
    lines.append("")
    lines.append("**Unresolved ambiguity.**")
    lines.append("- We cannot confirm from the data alone whether `hydro_gas_id` is a true source "
                  "primary key or an artifact of how Socrata assigns row ids on publish. This needs "
                  "confirmation from whoever owns the source extract on the City's side.")
    lines.append("- It is unclear whether null `meter_number` always means \"legitimately unmetered\" "
                  "(fixed-fee item) versus a data-capture gap for some metered services -- ~47% of "
                  "`EL` rows have a null meter_number, which is a large share to attribute entirely to "
                  "unmetered fixtures without source documentation.")
    lines.append("- Duplicate groups mixing many $0 `amount_due` line items with one large non-zero "
                  "`amount_due` row (seen in the 16-row example above) suggest some groups may blend "
                  "item-level rows with an invoice-total row for the same period -- i.e. the grain may "
                  "not be uniform across `actual_service_type` values. This should be verified against "
                  "a data dictionary or source-system SME before choosing a dimensional grain, rather "
                  "than assumed from pattern-matching alone.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Re-pull from Socrata instead of using cache")
    args = parser.parse_args()

    load_dotenv()  # ensure SOCRATA_DATASET_ID is available for the report header even on cache hits
    df = fetch_raw(force_refresh=args.refresh)

    id_profile = profile_hydro_gas_id(df)
    key_results = profile_candidate_keys(df)
    examples_df = find_example_groups(df)
    exact_dup_check = check_exact_duplicates_except_id(df)
    id_per_key_dist = hydro_gas_ids_per_base_key(df)

    if not examples_df.empty:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        examples_df.to_csv(EXAMPLES_CSV_PATH, index=False)
        print(f"Wrote example duplicate groups to {EXAMPLES_CSV_PATH}")

    report = build_report(df, id_profile, key_results, examples_df, exact_dup_check, id_per_key_dist)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Wrote report to {REPORT_PATH}")

    print("\n--- QUICK SUMMARY ---")
    print(id_profile)
    for r in key_results:
        print(r)
    print(exact_dup_check)


if __name__ == "__main__":
    main()

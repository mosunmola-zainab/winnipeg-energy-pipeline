# Data Modeling Decisions

This file records decisions actually made about the Winnipeg utility billing dataset's grain and identity. It reflects the current state of investigation only. It is not a design spec — no dimensions, fact tables, business rules, or deduplication logic have been defined yet.

Source evidence for everything below comes from raw-grain profiling of a 464,597-row snapshot on September 17, 2026 (exploratory script and full report kept locally, not in this public repo). See [`technical_history.md`](technical_history.md), Phase 6, for narrative context and the confirmed findings.

## Decision: raw grain is one record per `hydro_gas_id`

`hydro_gas_id` is unique and non-null across all 464,597 rows in the profiled snapshot. No other column or combination of columns tested is unique. Until further evidence changes this, the raw dataset's grain is treated as **one source record per `hydro_gas_id`**.

## Decision: `hydro_gas_id` is preserved, not dropped or replaced

`hydro_gas_id` is kept as the row-level identifier in any raw/ingested representation of this data, because it is currently the only column that reliably distinguishes one billed record from another. This holds even though its name suggests a customer- or meter-level identifier — behaviorally (uniqueness, no repetition across billing cycles) it looks more like a source-system surrogate or billing-line id. That mismatch is unresolved (see below) but does not change the decision to preserve it: dropping it in favor of a business key would lose the only confirmed unique reference to a record.

## Decision: business-key deduplication is unsafe without stronger evidence

None of the following are safe to deduplicate on, individually or combined, without further source confirmation:

- `account_number`
- `meter_number`
- `actual_service_type`
- `service_from_date` / `service_to_date`
- `service_address`
- `rate`
- `billing_units`
- `amount_due`

Even the fullest combination profiled (all of the above together) still produced 4,600 duplicate groups (48,276 rows) in the snapshot. Investigation of the largest duplicate groups showed the repetition is structural rather than accidental: accounts with `actual_service_type = 'OT'` (non-metered flat-fee items such as streetlights and signs) and many `EL` records have a null `meter_number`, so multiple genuinely distinct billed items (e.g. separate fixtures at one address) legitimately share the same account/meter/type/period values. Deduplicating on business fields would risk silently collapsing distinct billed line items into one. No deduplication logic is defined at this time.

## Known source ambiguities

These are open questions, not yet resolved:

- Whether `hydro_gas_id` is a genuine upstream source primary key, or an id assigned during Socrata's publishing pipeline, is unconfirmed.
- Whether a null `meter_number` always means "legitimately unmetered service," versus a data-capture gap for some metered services, is unconfirmed (roughly 47% of `EL` records have a null `meter_number`).
- Some duplicate groups mix many near-zero-`amount_due` rows with a single large-`amount_due` row under the same key. This may indicate a blend of line-level charge records and invoice-total-like records within the same `actual_service_type`, but this has not been confirmed against source documentation.

These should be resolved — via source-system documentation or a subject-matter expert — before any grain decision above is treated as final.

## Decision: the source has no verified facility identifier

No source column is a verified facility (physical site/building) identifier:

- `account_number` is a billing construct that can change over the life of what appears to be the same physical service point.
- `meter_number` is null for a large share of records and is not always stable to one address.
- `service_address` is the most stable of the candidates but is free text, not perfectly 1:1 with account, and cannot rule out one address hosting multiple distinct facilities.
- `customer_name` is a department/division label subject to formatting drift and reassignment over time, not a facility identifier.

None of `account_number`, `meter_number`, `service_address`, or `customer_name` should independently be treated as a facility identifier.

A facility entity may still be derivable later through enrichment/entity resolution — using `service_address`, `customer_name`, and account/meter context as matching attributes, combined with reliable external reference data. `service_address` in particular is a plausible matching attribute for that resolution, not a facility identifier on its own. Any future `dim_facility` would be an **enriched/conformed dimension** produced by that resolution process, not a direct copy or rename of a single source field. No such resolution logic is designed or implemented at this time.

## Bronze v1 Design

Bronze's structure has been agreed at a design level, based on direct inspection of the current ETL code and live checks against the Socrata API (see `technical_history.md` for the v1 pipeline this supersedes). No SQL or ETL code has been written yet — this section records the design, not an implementation.

**Storage.** PostgreSQL, in a dedicated `bronze` schema, with three tables:
- `bronze.ingestion_runs` — one row per ingestion attempt.
- `bronze.utility_billing_raw` — one row per source record per run.
- `bronze.current_snapshot` — a small pointer holding the `run_id` of the currently promoted successful run.

**Grain and identity.** `bronze.utility_billing_raw`'s primary key is `(run_id, hydro_gas_id)` — no surrogate row id. Each row stores the source record as JSONB, largely as received from Socrata (no casting, no dropped fields). `hydro_gas_id` is also stored as its own column, not as a business transformation, but because it is the Socrata-designated row identifier (confirmed via the dataset's `rowIdentifierColumnId` metadata) and is needed for deterministic ordering and indexing. Bronze performs no business or type transformations.

**Snapshots.** Full snapshots are preserved per `run_id` — the same `hydro_gas_id` recurs once per successful run, by design, not deduplicated across runs. A failed run must never replace the previous successful snapshot; `bronze.current_snapshot` only ever points at a run that completed and passed validation.

**Extraction.** Pagination is ordered by `hydro_gas_id`, the deterministic ordering key. 50,000 rows per page is the current tested starting point, not a permanent invariant — it may change as evidence warrants. HTTP requests for each page use bounded retry/backoff.

**Schema drift.** Each run records the set of source fields actually observed. A new non-critical field is recorded and warned about, not treated as a run failure.

**Validation.** A missing or non-unique `hydro_gas_id` fails validation for a run — this is also structurally enforced by the `(run_id, hydro_gas_id)` primary key itself. Bronze v1 does not include an arbitrary row-count percentage threshold as a validation check.

## Direction, not design: Silver/Gold

A layered architecture is the intended direction for the redesign; Bronze's design is recorded above. Silver and Gold remain direction only — as of this writing, no table structure, dimension, fact table, or transformation has been designed for either layer. This document will be updated once those decisions are actually made.

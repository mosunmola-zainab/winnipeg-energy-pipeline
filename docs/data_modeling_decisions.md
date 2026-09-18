# Data Modeling Decisions

This file records decisions actually made about the Winnipeg utility billing dataset's grain and identity. It reflects the current state of investigation only. It is not a design spec — no dimensions, fact tables, business rules, or deduplication logic have been defined yet.

Source evidence for everything below comes from raw-grain profiling of a 464,597-row snapshot on September 17, 2026 (exploratory script and full report kept locally, not in this public repo). See [`Document.md`](../Document.md), Phase 6, for narrative context and the confirmed findings.

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

## Direction, not design: Bronze/Silver/Gold

A layered (bronze/silver/gold) architecture is the intended direction for the redesign. As of this writing, no table structure, dimension, fact table, or transformation for any layer has been designed. This document will be updated once those decisions are actually made.

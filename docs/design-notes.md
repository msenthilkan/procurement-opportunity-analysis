# Design notes

Decisions made while building the pipeline, and the problems each one solved.

## Keep spend at one grain

The approver export repeats every requisition line once per approver. Joining it to spend would multiply spend by the number of approvers. Instead, approvers are collapsed to **one row per requisition** before the join, so the join can never add rows. The check is simple: Output must have exactly as many rows as the spend export.

## One buying channel per line

Catalogue status and contract linkage overlap: a catalogue line can also have a contract. Combining them into a single `Buying Channel` with a fixed priority (Catalogue, then Contract, then Non-catalogue, then Unclassified) makes every line count once. Every pivot and chart therefore sums to the true total.

## Replace manual VLOOKUPs with lookups in the query

The original process added two VLOOKUP columns to each approver export: one for email and one for procurement-group membership. These broke every month and produced `#N/A`. Both lookups now run in Power Query:

- Name to email from the user master, preferring **active** accounts when a name appears twice.
- Email to procurement group from a one-column list. Everyone not on the list is tagged Business/Finance.

Names that cannot be matched appear in `Approvers Not In List`, which plays the role the `#N/A` cells used to.

## Match taxonomy on short or long names, and show the gaps

Spend uses whichever commodity name the requester picked. The taxonomy is expanded so both the short and the long name point to the same row. Keys that map to more than one distinct row are flagged **Ambiguous** rather than picked at random. Unmatched commodities keep their source name with "(not in taxonomy)", so the category view still reconciles to 100%.

## Fast lookups

Lookups are built as records (`Record.FromTable` and `Record.FieldOrDefault`) after grouping. This avoids evaluating nested-join tables row by row, which was the main cause of slow refreshes.

## Robust to export changes

- Every input query has its automatic Changed Type step removed, because those steps hard-code column names.
- The supplier column is found by prefix, not exact name.
- `sum(Line Count)` falls back to a row count if it is missing or arrives as text.
- Unknown country codes surface as `CODE (not mapped)` instead of disappearing.

## Dates

The source exports text dates as M/D/YYYY. Parsing them with a day-first locale silently swapped day and month: 8/11 became 8 November instead of 11 August. The fix is to parse with `en-US` explicitly and to treat unparseable dates as blank rather than as errors. A quick sanity check also helped: no requisition can be dated in the future.

## Opportunity ranking

A running total is computed once over the buffered, sorted list. A commodity is **in scope** if the cumulative share *before* it is below the target, so the list always reaches the target. The suggested route uses buying frequency and value per line (catalogue) and supplier concentration (contract). Thresholds are settings at the top of the query, so they can be agreed with category managers and changed without touching the logic.

## Cross-check outside Excel

`scripts/preview_dashboard.py` re-implements the same rules in pandas. Running both on the sample data and comparing totals is a cheap way to catch logic errors.

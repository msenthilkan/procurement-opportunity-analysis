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

## P-card is a payment method, so it needs two entry points

Card spend reaches the data in two ways. An Ariba PO can be paid by card ("P-card on PO"): the line is in the spend export with payment method P-Card. Cardholders also buy directly from merchants: those transactions only exist on the issuer statement. Output handles the first; `qPCardOut` handles the second, and `qAllSpend` appends them.

Catalogue and contract keep priority over payment method: a catalogue order paid by card is still a catalogue order. The channel order is Catalogue, Contract, P-card on PO, Non-catalogue, Unclassified, and statement lines are always P-card (off-platform), so every line still counts once.

## No double counting between the PO and the card statement

A card-paid PO appears twice: once as a requisition line and once as a card transaction. The card feed carries the PO number, so `qPCardOut` drops any transaction whose PO number exists in Output. In the simulation all 309 card-paid POs are caught. If your issuer does not pass the PO number, match on supplier, amount and date within a few days instead, and check the reconciliation total after each refresh.

## Categorising card lines

The statement has no commodity. The query uses, in order: the commodity the cardholder chose at reconciliation, the L3 mapped from the merchant category code, and finally the MCC description itself. MCCs are broad (5045 covers computers and software), so the cardholder-coded commodity wins when present. MCCs outside the taxonomy keep their own policy in `qMCCMap`, which is how cash withdrawals and gambling are always flagged.

## Policy lives in the taxonomy

`P-card Policy` is a column on the taxonomy, so the category owner decides it once per L3, and both the compliance flags and the opportunity routes read the same value. For card lines outside the taxonomy, the MCC policy is used.

## Compliance flags are additive, compliance status is one value

A transaction can carry several flags (for example, restricted category and missing receipt), joined with "; ". `P-card Compliance` reduces them to one value: Non-compliant for blocked category, over limit, possible split or a catalogue/contract supplier; Review for restricted category or missing receipt; otherwise Compliant. Pivots on the single value always reconcile.

Split detection groups by cardholder, merchant and date. It flags only transactions under the limit whose group total is above it, which is the pattern a split leaves. Merchant names on statements often differ from Ariba supplier names, so the catalogue/contract supplier check is conservative; add a merchant-to-supplier mapping if you need it.

## The P-card route is about transactions, not spend

Averaging a whole commodity hides its tail: a category with a few large contracts and hundreds of small one-off orders looks like a contract category. The first version of the rule never fired in the simulation for exactly this reason. The rule now counts lines: if at least half the lines are already on card or are non-catalogue POs of 500 or less, and the category allows cards, the card fits the tail. Catalogue still wins when the frequency rule says catalogue. When the average line is large, the route says both, for example "Contract, consolidate suppliers + P-card for tail", and `P-card Action` gives the number of POs to move to card.

The frequency rules do not know about channels such as a travel booking tool, so a blocked-on-card category like hotels can still get a "Catalogue" suggestion. Category-level overrides belong in a scope matrix joined on the L3 name.

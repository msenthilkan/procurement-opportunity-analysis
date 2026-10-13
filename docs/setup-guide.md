# Setup guide

Builds the workbook from the seven input files. Works in Excel for Microsoft 365 or Excel 2019+ on Windows.

## 1. Folder

Put the seven files from `sample-data/` (or your own exports with the same columns) in one folder, then create a new workbook in the same folder, for example `Spend Opportunity Report.xlsx`. All queries, pivots and the dashboard live in this workbook.

| File | Query name | Contents |
| --- | --- | --- |
| qSpend.xlsx | `qSpend` | One row per requisition line |
| qApproverRaw.xlsx | `qApproverRaw` | Each line repeated once per approver |
| qTaxonomy.xlsx | `qTaxonomy` | Category taxonomy, Level 0 to Level 3 |
| qUserMaster.xlsx | `qUserMaster` | User names, active flag and email |
| tblProcurementGroup.xlsx | `qProcurementGroup` | One column, `Email`, listing procurement approvers |
| qPCard.xlsx | `qPCard` | Card issuer statement, one row per transaction, amounts in reporting currency |
| qMCCMap.xlsx | `qMCCMap` | Merchant category code to L3 commodity, with an MCC policy for codes outside the taxonomy |

`qTaxonomy` now has an optional `P-card Policy` column (Allowed, Restricted, Blocked). `qSpend` has an optional `[PO-P&I] Payment Method` column; lines containing "card" become **P-card on PO**. Both queries still work if these columns are missing.

**Card statement tips:** use the issuer's billing amount converted to your reporting currency; keep the PO number field if your card programme pays Ariba POs (Ariba "P-card on PO"), because that is how double counting is prevented.

## 2. Load the seven inputs

For each file:

1. **Data → Get Data → From File → From Workbook**, pick the file, select its sheet or table, then **Transform Data**.
2. If headers show as Column1, Column2 and so on, use **Home → Use First Row as Headers**.
3. **Delete the automatic "Changed Type" step.** It hard-codes every column name and breaks when an export changes. The Output query handles types itself.
4. Rename the query as in the table above.

## 3. Add the four queries

In this order: `Output`, `qAllSpend`, `qOpportunities`. With a P-card programme, also add `qPCardOut` after Output and switch on the card line in `qAllSpend` (see its header comment). Without one, skip `qPCardOut` and the two card input files.

1. **Home → New Source → Other Sources → Blank Query**.
2. **Advanced Editor**, delete everything, and paste the matching file from `powerquery/`.
3. Rename the query to match the file name.

In `Output.pq`, check the settings block at the top: the taxonomy code column, the user master name and email columns, and the `CountryMap` codes. In `qPCardOut.pq`, set `SingleLimit` and the card export column names. In `qOpportunities.pq`, review the P-card thresholds (`PCardLineMax`, `PCardMinShare`).

## 3b. Optional: scope tiers and P-card policy from a scope matrix

If you keep a scope matrix (an Excel table `tblScopeMatrix` with columns `L3 Commodity`, `Scope Tier`, `Proposed Route`, `P-card Policy`) in the workbook:

1. Rename the raw taxonomy query to `qTaxonomyRaw`.
2. Add a blank query named `qTaxonomy` and paste `powerquery/qTaxonomyPolicy.pq`.
3. Output and qPCardOut then carry `Taxonomy.Scope Tier`, `Taxonomy.Proposed Route` and `Taxonomy.P-card Policy`.
4. In `qOpportunities`, `ExcludeTiers = {"D", "E"}` leaves other-channel and non-addressable spend out of the ranking, tier C takes the category route, and a "Catalogue" suggestion is replaced by the category route where the playbook rules out a catalogue.

Without the matrix these columns are blank and every query behaves as before.

## 4. Load destinations

- **Close & Load To… → Only Create Connection** for the seven inputs and for `qPCardOut`.
- `Output` → **Table** on a new sheet. Confirm the table name is `Output` (**Table Design → Table Name**).
- `qAllSpend` → **Table** on a new sheet named `AllSpend`, table name `AllSpend`. Build the pivots on this table.
- `qOpportunities` → **Table** on a new sheet named `Opportunities`.

## 5. Checks after each refresh

- [ ] Row count of Output equals the spend export (the joins never add rows).
- [ ] Total spend equals the source report total.
- [ ] `Taxonomy Match` other than Matched: add the missing commodities to the taxonomy.
- [ ] `Approvers Not In List`: names not found in the user master.
- [ ] `Country` values ending in "(not mapped)": add the code to `CountryMap`.
- [ ] AllSpend rows = Output rows + card statement rows − card rows whose PO number is in Output.
- [ ] Card total in AllSpend = card statement total − card-paid PO total (no double count).
- [ ] Card lines with Taxonomy Match = Unmapped: add the MCC to `qMCCMap` or the commodity to the taxonomy.

## Monthly refresh

Save new exports over the same files, then **Data → Refresh All** twice (queries first, then pivots).

## Troubleshooting

| Message | Fix |
| --- | --- |
| The column '…' of the table wasn't found | A column name differs from the code. If it is in an input query, delete its Changed Type step. If it is in Output, update the settings block. |
| Token 'else' expected | A partial paste lost a line. Replace the whole query with the file from `powerquery/`. |
| Month shows the wrong month | Source dates are M/D/YYYY. Leave `ToDate` on `en-US` unless your export differs. |
| Lines / Avg Spend per Line show Error | Fixed in `qOpportunities.pq`: it falls back to counting rows when `sum(Line Count)` is missing or text. |

# Dashboard pivots

Build every pivot from the `Output` table (**Insert → PivotTable**) on a sheet named `Pivots`. Use one spend measure everywhere; the examples use `sum(PO Spend)`.

Layout for every pivot: **Design → Report Layout → Show in Tabular Form**, **Subtotals → Do Not Show**, number format `#,##0`.

## KPI cards

| Card | Formula | Format |
| --- | --- | --- |
| Total spend | `=SUM(Output[sum(PO Spend)])` | `"€"#,##0,,"M"` |
| Non-catalogue spend | `=SUMIFS(Output[sum(PO Spend)],Output[Buying Channel],"Non-catalogue")+SUMIFS(Output[sum(PO Spend)],Output[Buying Channel],"Unclassified")` | `"€"#,##0,,"M"` |
| Off-catalogue share | `=NonCat / Total` | `0.0%` |
| Opportunity coverage | `=SUMIFS(qOpportunities[Non-catalogue Spend],qOpportunities[In Scope],"Yes")/SUM(qOpportunities[Non-catalogue Spend])` | `0%` |
| Candidates identified | `=COUNTIFS(qOpportunities[In Scope],"Yes")` | `0` |

`,,` in a number format divides by one million.

## Pivot A: spend by country

- Rows: `Country`; Values: `sum(PO Spend)`; sort smallest to largest so the largest bar sits at the top.
- PivotChart: Clustered Bar. To show millions, set the value field's number format to `#,##0,,` (**Value Field Settings → Number Format**); chart labels follow it.

## Pivot B: non-catalogue spend by country

Same as A, with `Buying Channel` in Filters (Non-catalogue and Unclassified ticked).

## Pivot C: catalogue vs non-catalogue by country

- Rows: `Country`; Columns: `Buying Channel` (or `Channel Group`); Values: `sum(PO Spend)`.
- Non-catalogue % beside the pivot: `=IFERROR((NonCat + Unclassified) / GrandTotal, 0)`, filled down.

## Pivot D: non-catalogue spend by category and lead

- Filters: `Buying Channel` = Non-catalogue, Unclassified.
- Rows: `Taxonomy.Procurement Or Business Led`, then `Taxonomy.Level 1 (Family)`.
- Values: `sum(PO Spend)` twice; set the second to **Show Values As → % of Grand Total**.
- **Report Layout → Repeat All Item Labels**; sort descending within each group.
- A `(blank)` lead is spend not in the taxonomy. Keep it so the table reconciles to 100%.

## Pivot E: monthly trend

- Rows: `Month`; Columns: `Buying Channel`; Values: `sum(PO Spend)`; Stacked Column chart; format Month as `mmm-yyyy`.

## Opportunity Pareto

On the Opportunities sheet, select `Commodity`, `Non-catalogue Spend` and `Cumulative Share` for the top 20 rows, then **Insert → Combo**: spend as clustered column, cumulative share as a line on the secondary axis.

## Slicers

Insert slicers for `Country` and `Month`, then use **Report Connections** to link them to every pivot. KPI formulas and the Pareto chart show the full period.

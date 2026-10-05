// qOpportunities.pq
// Ranks non-catalogue spend by commodity (Pareto), flags the commodities that together
// cover the target share, sets a priority and suggests a catalogue or contract route.
// Input: the Output query. Load this query to a sheet.
let
    // ===== Settings: adjust to your spend levels =====
    Target     = 0.75,   // share of non-catalogue spend to cover
    MinLines   = 20,     // catalogue candidate: at least this many lines...
    MaxAvgLine = 1000,   // ...and average spend per line at or below this
    IncludeUnclassified = true,

    Src = Output,
    Spend = "sum(Requisition Spend)",
    Org   = "Country",
    // Finds the supplier column whatever its exact name ([REQ]Supplier (...))
    Sup   = List.First(List.Select(Table.ColumnNames(Src),
                each Text.StartsWith(_, "[REQ]Supplier")), "[REQ]Supplier (Common Supplier)"),

    Non = Table.SelectRows(Src, each [Buying Channel] = "Non-catalogue"
        or (IncludeUnclassified and [Buying Channel] = "Unclassified")),

    // Commodity name: taxonomy name, or the source commodity if not in taxonomy
    Named = Table.AddColumn(Non, "_Cat", each
        let l3 = [#"Taxonomy.Level 3 (Commodity) - Long"],
            l2 = [#"Taxonomy.Level 2 (Category)"],
            raw = [#"[REQ]Commodity (Commodity (L3))"]
        in if l3 <> null and l3 <> "" then [Commodity = l3, Category = l2]
           else [Commodity = (if raw = null or raw = "" then "Blank commodity"
                              else Text.From(raw) & " (not in taxonomy)"),
                 Category = "Not in taxonomy"]),
    Expanded = Table.ExpandRecordColumn(Named, "_Cat", {"Commodity", "Category"}),

    Grouped = Table.Group(Expanded, {"Commodity", "Category"}, {
        {"Non-catalogue Spend", each List.Sum(Table.Column(_, Spend)), type nullable number},
        {"Lines", each if Table.HasColumns(_, "sum(Line Count)")
            then List.Sum(List.Transform(Table.Column(_, "sum(Line Count)"),
                each try Number.From(_) otherwise 0))
            else Table.RowCount(_), type number},
        {"Requisitions", each List.Count(List.Distinct([#"[REQ] Requisition ID"])), Int64.Type},
        {"Suppliers", each List.Count(List.Distinct(Table.Column(_, Sup))), Int64.Type},
        {"Countries", each Text.Combine(List.Sort(List.Distinct(List.Transform(
            Table.Column(_, Org), each if _ = null then "Blank" else Text.From(_)))), ", "), type text},
        {"_Top", each Table.Max(Table.Group(_, {Sup},
            {{"S", each List.Sum(Table.Column(_, Spend)), type nullable number}}), "S")}
    }),
    Positive = Table.SelectRows(Grouped, each [#"Non-catalogue Spend"] <> null
        and [#"Non-catalogue Spend"] > 0),

    // Suggested route
    Metrics = Table.AddColumn(Positive, "_M", each
        let s = [#"Non-catalogue Spend"],
            lines = if [Lines] = null or [Lines] = 0 then 1 else [Lines],
            avg = s / lines,
            top = [_Top],
            share = if top = null or top[S] = null then 0 else top[S] / s,
            route = if lines >= MinLines and avg <= MaxAvgLine then "Catalogue"
                else if share >= 0.6 then "Contract with top supplier"
                else if [Suppliers] >= 5 then "Contract, consolidate suppliers"
                else "Contract"
        in [Avg = avg, TopSupplier = if top = null then null else Record.Field(top, Sup),
            TopShare = share, Route = route]),
    WithM = Table.ExpandRecordColumn(Metrics, "_M", {"Avg", "TopSupplier", "TopShare", "Route"},
        {"Avg Spend per Line", "Top Supplier", "Top Supplier Share", "Suggested Route"}),

    // Rank, cumulative share, scope and priority
    Sorted = Table.Buffer(Table.Sort(Table.RemoveColumns(WithM, {"_Top"}),
        {{"Non-catalogue Spend", Order.Descending}})),
    Amounts = Sorted[#"Non-catalogue Spend"],
    Total = List.Sum(Amounts),
    Running = List.Skip(List.Accumulate(Amounts, {0}, (acc, x) => acc & {List.Last(acc) + x})),
    Combined = Table.FromColumns(Table.ToColumns(Sorted) & {List.Positions(Amounts), Running},
        Table.ColumnNames(Sorted) & {"_i", "_Cum"}),
    Ranked = Table.AddColumn(Combined, "Rank", each [_i] + 1, Int64.Type),
    Share = Table.AddColumn(Ranked, "Share of Non-catalogue",
        each [#"Non-catalogue Spend"] / Total, Percentage.Type),
    Cum = Table.AddColumn(Share, "Cumulative Share", each [_Cum] / Total, Percentage.Type),
    Scope = Table.AddColumn(Cum, "In Scope", each
        if ([_Cum] - [#"Non-catalogue Spend"]) / Total < Target then "Yes" else "No", type text),
    Priority = Table.AddColumn(Scope, "Priority", each
        let before = ([_Cum] - [#"Non-catalogue Spend"]) / Total
        in if before < 0.5 then "High" else if before < Target then "Medium" else "Low", type text),
    Final = Table.SelectColumns(Priority, {"Rank", "Category", "Commodity", "Non-catalogue Spend",
        "Share of Non-catalogue", "Cumulative Share", "In Scope", "Priority", "Suggested Route",
        "Lines", "Requisitions", "Suppliers", "Top Supplier", "Top Supplier Share",
        "Avg Spend per Line", "Countries"}),
    Typed = Table.TransformColumnTypes(Final, {
        {"Category", type text}, {"Commodity", type text}, {"Non-catalogue Spend", type number},
        {"Lines", type number}, {"Requisitions", Int64.Type}, {"Suppliers", Int64.Type},
        {"Top Supplier", type text}, {"Top Supplier Share", Percentage.Type},
        {"Avg Spend per Line", type number}, {"Countries", type text}})
in
    Typed

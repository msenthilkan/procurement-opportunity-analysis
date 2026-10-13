// qOpportunities.pq
// Ranks non-catalogue spend by commodity (Pareto), flags the commodities that together
// cover the target share, sets a priority and suggests a catalogue, contract or P-card route.
// Input: qAllSpend (Ariba requisitions + off-platform P-card). Load this query to a sheet.
let
    // ===== Settings: adjust to your spend levels =====
    Target     = 0.75,   // share of non-catalogue spend to cover
    MinLines   = 20,     // catalogue candidate: at least this many lines...
    MaxAvgLine = 1000,   // ...and average spend per line at or below this
    IncludeUnclassified = true,
    IncludePCard = true,      // count card spend (on PO and off-platform) as off-catalogue
    ExcludeTiers = {"D", "E"},// scope tiers left out of the ranking (other channel / non-addressable);
                              // only applies when the taxonomy has a Scope Tier (qTaxonomyPolicy.pq)
    PCardLineMax = 500,       // P-card candidate: a non-catalogue requisition line at or below this value...
    PCardMinShare = 0.5,      // ...P-card fits when candidate + card lines are at least this share of all lines.
                              // Whole commodity -> "P-card (tail spend)" only if average line <= MaxAvgLine;
                              // otherwise "<contract route> + P-card for tail".
                              // ...and only where the category's P-card Policy is "Allowed"

    Src = qAllSpend,
    // P-card logic switches itself off when there are no card lines (no card programme):
    // no P-card route, no P-card action, and the P-card columns are dropped from the output.
    UsePCard = not Table.IsEmpty(Table.SelectRows(Src, each [Channel Group] = "P-card")),
    Spend = "sum(Requisition Spend)",
    Org   = "Country",
    // Finds the supplier column whatever its exact name ([REQ]Supplier (...))
    Sup   = List.First(List.Select(Table.ColumnNames(Src),
                each Text.StartsWith(_, "[REQ]Supplier")), "[REQ]Supplier (Common Supplier)"),

    Non = Table.SelectRows(Src, each [Buying Channel] = "Non-catalogue"
        or (IncludeUnclassified and [Buying Channel] = "Unclassified")
        or (UsePCard and IncludePCard and [Channel Group] = "P-card")),
    TierCode = (t as any) as text => if t = null then "" else Text.Start(Text.Trim(Text.From(t)), 1),
    InScopeTiers = Table.SelectRows(Non, each not List.Contains(ExcludeTiers, TierCode([#"Taxonomy.Scope Tier"]))),

    // Commodity name: taxonomy name, or the source commodity if not in taxonomy
    Named = Table.AddColumn(InScopeTiers, "_Cat", each
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
        {"P-card Spend", each List.Sum(Table.Column(
            Table.SelectRows(_, each [Channel Group] = "P-card"), Spend)), type nullable number},
        {"P-card Lines", each Table.RowCount(Table.SelectRows(_, each [Channel Group] = "P-card")), Int64.Type},
        {"P-card Candidate Lines", each Table.RowCount(Table.SelectRows(_, each
            List.Contains({"Non-catalogue", "Unclassified"}, [Buying Channel])
            and Record.Field(_, Spend) <> null and Record.Field(_, Spend) <= PCardLineMax)), Int64.Type},
        {"P-card Candidate Spend", each List.Sum(List.Select(Table.Column(Table.SelectRows(_, each
            List.Contains({"Non-catalogue", "Unclassified"}, [Buying Channel])), Spend),
            each _ <> null and _ <= PCardLineMax)), type nullable number},
        {"P-card Policy", each List.First(List.RemoveNulls(
            Table.Column(_, "Taxonomy.P-card Policy") & Table.Column(_, "P-card Policy")), null), type text},
        {"Scope Tier", each List.First(List.RemoveNulls(Table.Column(_, "Taxonomy.Scope Tier")), null), type text},
        {"Category Route", each List.First(List.RemoveNulls(Table.Column(_, "Taxonomy.Proposed Route")), null), type text},
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
            policy = if UsePCard then [#"P-card Policy"] else null,
            cand = if [#"P-card Candidate Spend"] = null then 0 else [#"P-card Candidate Spend"],
            catRoute = [Category Route],
            tier = TierCode([Scope Tier]),
            freq = if lines >= MinLines and avg <= MaxAvgLine then "Catalogue"
                else if share >= 0.6 then "Contract with top supplier"
                else if [Suppliers] >= 5 then "Contract, consolidate suppliers"
                else "Contract",
            // Category playbook wins for business-led tiers, and wherever it rules out a catalogue
            base = if catRoute = null then freq
                else if tier = "C" then catRoute
                else if freq = "Catalogue" and not Text.Contains(catRoute, "Catalogue") then catRoute
                else freq,
            tailFit = policy = "Allowed"
                and ([#"P-card Candidate Lines"] + [#"P-card Lines"]) / lines >= PCardMinShare,
            route = if [Category] = "Not in taxonomy" and policy = "Blocked"
                    then "Prohibited: follow up with cardholder"
                else if [Category] = "Not in taxonomy" and policy = "Restricted"
                    then "Card policy review (T&E or other channel)"
                else if tailFit and base = "Catalogue" then "Catalogue"
                else if tailFit and avg <= MaxAvgLine then "P-card (tail spend)"
                else if tailFit then base & " + P-card for tail"
                else base
        in [Avg = avg, TopSupplier = if top = null then null else Record.Field(top, Sup),
            TopShare = share, Route = route,
            CardAction = let card = if [#"P-card Spend"] = null then 0 else [#"P-card Spend"] in
                if not UsePCard then null
                else if card = 0 then
                    (if policy = "Allowed" and cand > 0
                     then "Move " & Text.From([#"P-card Candidate Lines"]) & " low-value POs to card" else null)
                else if Text.StartsWith(route, "Prohibited") or Text.StartsWith(route, "Card policy") then route
                else if policy = "Blocked" then "Stop card use; move to " & route
                else if policy = "Restricted" then "Review card use; prefer " & route
                else if Text.Contains(route, "P-card") then "Keep on card" &
                    (if [#"P-card Candidate Lines"] > 0 then "; move " & Text.From([#"P-card Candidate Lines"])
                     & " low-value POs to card" else "")
                else "Card allowed; consider " & route]),
    WithM = Table.ExpandRecordColumn(Metrics, "_M", {"Avg", "TopSupplier", "TopShare", "Route", "CardAction"},
        {"Avg Spend per Line", "Top Supplier", "Top Supplier Share", "Suggested Route", "P-card Action"}),

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
    CardOutCols = {"P-card Spend", "P-card Policy", "P-card Action", "P-card Candidate Lines", "P-card Candidate Spend"},
    Final0 = Table.SelectColumns(Priority, {"Rank", "Category", "Commodity", "Non-catalogue Spend",
        "Share of Non-catalogue", "Cumulative Share", "In Scope", "Priority", "Scope Tier", "Suggested Route", "Category Route",
        "P-card Spend", "P-card Policy", "P-card Action", "P-card Candidate Lines", "P-card Candidate Spend",
        "Lines", "Requisitions", "Suppliers", "Top Supplier", "Top Supplier Share",
        "Avg Spend per Line", "Countries"}),
    Final = if UsePCard then Final0 else Table.RemoveColumns(Final0, CardOutCols),
    Types = {
        {"Category", type text}, {"Commodity", type text}, {"Non-catalogue Spend", type number},
        {"Lines", type number}, {"Requisitions", Int64.Type}, {"Suppliers", Int64.Type},
        {"Top Supplier", type text}, {"P-card Spend", type number}, {"P-card Action", type text},
        {"P-card Candidate Spend", type number}, {"Top Supplier Share", Percentage.Type},
        {"Avg Spend per Line", type number}, {"Countries", type text}},
    // Only type the columns that are present (P-card columns are dropped without card data)
    Typed = Table.TransformColumnTypes(Final, List.Select(Types, each Table.HasColumns(Final, _{0})))
in
    Typed

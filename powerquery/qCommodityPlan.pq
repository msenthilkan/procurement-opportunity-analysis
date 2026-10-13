// qCommodityPlan.pq
// One row per L3 commodity: where it is bought, how much is already on catalogue/contract,
// the quick wins by country, and the recommended approach across countries.
// Input: qCountryActions. Load this query to a sheet (table "qCommodityPlan").
let
    RegionalMinCountries = 3,   // bought off-catalogue in this many countries -> one regional agreement

    Src = qCountryActions,
    Grouped = Table.Group(Src, {"Commodity"}, {
        {"Category", each List.First(List.RemoveNulls([Category]), null), type text},
        {"Scope Tier", each List.First([Scope Tier]), type text},
        {"Owner", each List.First(List.RemoveNulls([Owner]), null), type text},
        {"Category Route", each List.First(List.RemoveNulls([Category Route]), null), type text},
        {"Off-catalogue Spend", each List.Sum([#"Off-catalogue Spend"]), type number},
        {"On-catalogue/Contract Spend", each List.Sum([#"On-catalogue/Contract Spend"]), type number},
        {"Countries", each List.Count(List.Distinct([Country])), Int64.Type},
        {"Top Countries", each Text.Combine(List.FirstN(
            Table.Sort(_, {{"Off-catalogue Spend", Order.Descending}})[Country], 3), ", "), type text},
        {"Quick Win Countries", each Text.Combine(List.Sort(List.Distinct(
            Table.SelectRows(_, each Text.StartsWith([Action Type], "Quick win"))[Country])), ", "), type text},
        {"Quick Win Spend", each List.Sum(Table.SelectRows(_, each
            Text.StartsWith([Action Type], "Quick win"))[#"Off-catalogue Spend"]), type nullable number},
        {"Replicate Countries", each Text.Combine(List.Sort(List.Distinct(
            Table.SelectRows(_, each [Action Type] = "Replicate other country")[Country])), ", "), type text},
        {"Main Supplier", each let t = Table.Group(_, {"Top Supplier"},
            {{"S", each List.Sum([#"Off-catalogue Spend"]), type number}}) in Table.Max(t, "S")[Top Supplier], type text},
        {"Best Priority", each List.First(List.Select({"High", "Medium", "Low", "Excluded"},
            (p) => List.Contains([Priority], p))), type text}
    }),
    WithCov = Table.AddColumn(Grouped, "Current Coverage", each
        let tot = [#"Off-catalogue Spend"] + [#"On-catalogue/Contract Spend"]
        in if tot = 0 then 0 else [#"On-catalogue/Contract Spend"] / tot, Percentage.Type),
    Plan = Table.AddColumn(WithCov, "Recommended Approach", each
        let t = Text.Start([Scope Tier], 1),
            route = if [Category Route] = null then "the category playbook route"
                    else Text.TrimEnd(Text.Trim([Category Route]), "."),
            n = [Countries],
            quick = [Quick Win Countries],
            rep = [Replicate Countries],
            scale = if n >= RegionalMinCountries
                then "one regional agreement covering " & Text.From(n) & " countries (start with " & [Top Countries] & ")"
                else "local agreements in " & [Top Countries],
            parts = List.RemoveNulls({
                if quick <> "" then "Quick wins now in " & quick & ": enforce or extend the existing agreements." else null,
                if rep <> "" then "Copy an existing country set-up for " & rep & "." else null,
                "Target " & scale & ", via " & route & "."}),
            steps = List.Transform(List.Positions(parts), each Text.From(_ + 1) & ") " & parts{_})
        in if [Scope Tier] = "Not classified" then "Classify first: add this commodity to the taxonomy / scope matrix, then refresh."
           else if t = "E" then "Exclude: non-addressable (" & route & "). Report as exclusion."
           else if t = "D" then "Exclude from catalogue target: bought via " & route & "."
           else if t = "C" then "Business-led: " & route & ". Procurement reviews terms; " & scale & " where the business agrees."
           else Text.Combine(steps, " "), type text),
    Sorted = Table.Sort(Plan, {{"Off-catalogue Spend", Order.Descending}}),
    Final = Table.SelectColumns(Sorted, {"Category", "Commodity", "Scope Tier", "Best Priority",
        "Recommended Approach", "Owner", "Off-catalogue Spend", "On-catalogue/Contract Spend", "Current Coverage",
        "Countries", "Top Countries", "Quick Win Countries", "Quick Win Spend", "Replicate Countries",
        "Main Supplier", "Category Route"})
in
    Final

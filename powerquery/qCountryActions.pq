// qCountryActions.pq
// One row per Country x L3 commodity with off-catalogue spend, and a practical, specific action.
// The action compares countries: a supplier or commodity already on catalogue/contract in one
// country is the fastest route for another country.
// Inputs: Output (with Taxonomy.Scope Tier / Taxonomy.Proposed Route from qTaxonomyPolicy)
//         tblScopeMatrix (optional columns: Lead, Practical solution)
// Load this query to a sheet (table "qCountryActions").
let
    // ===== Settings =====
    SpendCol = "sum(PO Spend)",       // same measure as your pivots
    MinSpend = 0,                     // ignore country x commodity cells at or below this spend
    RegionalMinCountries = 2,         // same top supplier off-catalogue in this many countries -> regional deal
    HighCut = 0.5,                    // priority High: first 50% of a country's addressable off-catalogue spend
    MediumCut = 0.8,                  // priority Medium: up to 80%; Low after that

    // ===== Helpers =====
    Clean = (x as any) as text =>
        if x = null then "" else Text.Combine(List.Select(Text.SplitAny(
            Text.Replace(Text.From(x), Character.FromNumber(160), " "),
            " #(tab)#(cr)#(lf)"), each _ <> ""), " "),
    Key = (x as any) as text => Text.Lower(Clean(x)),
    Nz = (x as any) as number => if x = null then 0 else x,
    ListText = (l as list) as text => Text.Combine(List.Sort(List.Distinct(l)), ", "),
    // Record.FromTable needs unique names: keep the first row per key
    ToLookup = (t as table, keyCol as text, valueCol as text) as record =>
        Record.FromTable(Table.RenameColumns(
            Table.SelectColumns(Table.Distinct(t, {keyCol}), {keyCol, valueCol}),
            {{keyCol, "Name"}, {valueCol, "Value"}})),

    // ===== 1. One slim row per spend line =====
    Src = Output,
    SupCol = List.First(List.Select(Table.ColumnNames(Src), each Text.StartsWith(_, "[REQ]Supplier")),
        "[REQ]Supplier (Common Supplier)"),
    HasLines = Table.HasColumns(Src, "sum(Line Count)"),
    Base = Table.AddColumn(Src, "_R", each
        let l3 = [#"Taxonomy.Level 3 (Commodity) - Long"],
            raw = [#"[REQ]Commodity (Commodity (L3))"],
            tier = [#"Taxonomy.Scope Tier"],
            sup = Record.Field(_, SupCol),
            amt = try Number.From(Record.Field(_, SpendCol)) otherwise null
        in [Commodity = if l3 <> null and l3 <> "" then l3
                        else if raw = null or raw = "" then "Blank commodity"
                        else Text.From(raw) & " (not in taxonomy)",
            Category = [#"Taxonomy.Level 2 (Category)"],
            Tier = if tier = null or tier = "" then "Not classified" else tier,
            Route = [#"Taxonomy.Proposed Route"],
            Amount = Nz(amt),
            Lines = if HasLines then (try Nz(Number.From([#"sum(Line Count)"])) otherwise 1) else 1,
            Supplier = if sup = null or Clean(sup) = "" then "(blank supplier)" else Clean(sup),
            Channel = [Buying Channel]]),
    Rows = Table.Buffer(Table.ExpandRecordColumn(Table.SelectColumns(Base, {"Country", "_R"}), "_R",
        {"Commodity", "Category", "Tier", "Route", "Amount", "Lines", "Supplier", "Channel"})),
    OnRows = Table.SelectRows(Rows, each List.Contains({"Catalogue", "Contract"}, [Channel])),
    OffRows = Table.SelectRows(Rows, each not List.Contains({"Catalogue", "Contract"}, [Channel])),

    // ===== 2. What is already on catalogue/contract =====
    ChannelName = (chs as list) as text =>
        if List.Contains(chs, "Catalogue") and List.Contains(chs, "Contract") then "catalogue and contract"
        else if List.Contains(chs, "Catalogue") then "catalogue" else "contract",
    // a) same country, commodity and supplier
    OnSame = Table.Group(Table.AddColumn(OnRows, "_k", each
            Key([Country]) & "|" & Key([Commodity]) & "|" & Key([Supplier]), type text),
        {"_k"}, {{"V", each ChannelName([Channel])}}),
    OnSameLookup = ToLookup(OnSame, "_k", "V"),
    // b) same commodity and supplier, any country
    OnSup = Table.Group(Table.AddColumn(OnRows, "_k", each Key([Commodity]) & "|" & Key([Supplier]), type text),
        {"_k"}, {{"V", each [Countries = List.Distinct([Country]), Ch = ChannelName([Channel])]}}),
    OnSupLookup = ToLookup(OnSup, "_k", "V"),
    // c) same commodity, any supplier, any country
    OnCom = Table.Group(Table.AddColumn(OnRows, "_k", each Key([Commodity]), type text),
        {"_k"}, {{"V", each [Countries = List.Distinct([Country]), Ch = ChannelName([Channel]),
                             Suppliers = List.Distinct([Supplier])]}}),
    OnComLookup = ToLookup(OnCom, "_k", "V"),
    // d) on-platform spend per country x commodity (for coverage)
    OnCell = Table.Group(Table.AddColumn(OnRows, "_k", each Key([Country]) & "|" & Key([Commodity]), type text),
        {"_k"}, {{"V", each List.Sum([Amount]), type number}}),
    OnCellLookup = ToLookup(OnCell, "_k", "V"),

    // ===== 3. Off-catalogue spend per country x commodity =====
    Cells = Table.Group(OffRows, {"Country", "Commodity"}, {
        {"Category", each List.First(List.RemoveNulls([Category]), null), type text},
        {"Scope Tier", each List.First([Tier]), type text},
        {"Category Route", each List.First(List.RemoveNulls([Route]), null), type text},
        {"Off-catalogue Spend", each List.Sum([Amount]), type number},
        {"Lines", each List.Sum([Lines]), type number},
        {"Suppliers", each List.Count(List.Distinct([Supplier])), Int64.Type},
        {"_Top", each Table.Max(Table.Group(_, {"Supplier"}, {{"S", each List.Sum([Amount]), type number}}), "S")}}),
    Positive = Table.SelectRows(Cells, each [#"Off-catalogue Spend"] > MinSpend),
    WithTop = Table.AddColumn(Table.AddColumn(Positive, "Top Supplier", each [_Top][Supplier], type text),
        "Top Supplier Share", each if [#"Off-catalogue Spend"] = 0 then 0
            else [_Top][S] / [#"Off-catalogue Spend"], Percentage.Type),

    // Same top supplier off-catalogue in several countries -> regional deal
    TopKeyed = Table.AddColumn(WithTop, "_tk", each Key([Commodity]) & "|" & Key([Top Supplier]), type text),
    RegionalCount = Table.Group(TopKeyed, {"_tk"}, {{"V", each List.Count(List.Distinct([Country])), Int64.Type}}),
    RegionalLookup = ToLookup(RegionalCount, "_tk", "V"),

    // ===== 4. Scope matrix: owner and playbook steps (optional columns) =====
    M0 = Table.TransformColumnNames(tblScopeMatrix, each Clean(_)),
    MCols = Table.ColumnNames(M0),
    L3Col = List.First(List.Select({"L3 Commodity", "L3 Scope Matrix", "L3 Long"}, each List.Contains(MCols, _)), null),
    MatrixLookup = if L3Col = null then [] else Record.FromTable(Table.FromRecords(List.Transform(
        Table.ToRecords(Table.Distinct(Table.SelectRows(
            Table.AddColumn(M0, "_k", each Key(Record.Field(_, L3Col)), type text), each [_k] <> ""), {"_k"})),
        each [Name = [_k], Value = [
            Lead = Record.FieldOrDefault(_, "Lead", null),
            Steps = Record.FieldOrDefault(_, "Practical solution", null)]]))),

    // ===== 5. The action =====
    Act = Table.AddColumn(TopKeyed, "_A", each
        let tier = [Scope Tier],
            t = Text.Start(tier, 1),
            route = if [Category Route] = null then "the category playbook route"
                    else Text.TrimEnd(Text.Trim([Category Route]), "."),
            ctry = [Country], com = [Commodity], top = [Top Supplier],
            same = Record.FieldOrDefault(OnSameLookup, Key(ctry) & "|" & Key(com) & "|" & Key(top), null),
            sup = Record.FieldOrDefault(OnSupLookup, Key(com) & "|" & Key(top), null),
            supOther = if sup = null then {} else List.RemoveItems(sup[Countries], {ctry}),
            comOn = Record.FieldOrDefault(OnComLookup, Key(com), null),
            comOther = if comOn = null then {} else List.RemoveItems(comOn[Countries], {ctry}),
            regional = Record.FieldOrDefault(RegionalLookup, [_tk], 1),
            m = Record.FieldOrDefault(MatrixLookup, Key(com), [Lead = null, Steps = null]),
            r =
            if t = "E" then [Type = "Exclude (non-addressable)",
                Action = "Out of procurement scope: " & route & ".",
                Next = "Agree with Finance to move these lines off requisitions; report as an exclusion, not as non-compliance."]
            else if t = "D" then [Type = "Exclude (other channel)",
                Action = "Bought through another channel: " & route & ".",
                Next = "Remove from the Ariba catalogue target; report this spend separately with its channel owner."]
            else if tier = "Not classified" then [Type = "Classify first",
                Action = if Text.EndsWith(com, "(not in taxonomy)")
                    then "Commodity is not in the taxonomy (or matches more than one L3), so it has no scope decision."
                    else "Commodity is in the taxonomy but not in the scope matrix, so it has no scope decision.",
                Next = if Text.EndsWith(com, "(not in taxonomy)")
                    then "Add the L3 to the taxonomy or fix the commodity on the requisitions; then add it to the scope matrix and refresh."
                    else "Add a row to the scope matrix (Scope Tier, Proposed Route) and refresh; the row then gets a sourcing action."]
            else if same <> null then [Type = "Quick win: leakage",
                Action = top & " already has a " & same & " in " & ctry & " for " & com
                    & ", yet " & Text.From(Number.Round([Top Supplier Share] * 100, 0)) & "% of this off-catalogue spend still goes to "
                    & top & " outside it.",
                Next = "Point requesters to the existing " & same & "; block free-text orders to " & top
                    & " for this commodity; brief the top requesters."]
            else if List.Count(supOther) > 0 then [Type = "Quick win: extend agreement",
                Action = top & " is already on " & sup[Ch] & " in " & ListText(supOther)
                    & "; extend that agreement to " & ctry & ".",
                Next = "Ask the " & ListText(supOther) & " category owner for the terms; request " & top
                    & " to add " & ctry & " (same prices or a local price list); load it in Ariba."]
            else if List.Count(comOther) > 0 then [Type = "Replicate other country",
                Action = com & " is already on " & comOn[Ch] & " in " & ListText(comOther)
                    & " (" & ListText(List.FirstN(comOn[Suppliers], 3)) & "); use that set-up for " & ctry & ".",
                Next = "Use the " & ListText(comOther) & " contract/catalogue as template; invite "
                    & top & " and the existing supplier to quote; award and load in Ariba."]
            else if regional >= RegionalMinCountries then [Type = "Regional deal",
                Action = top & " is the top off-catalogue supplier for " & com & " in "
                    & Text.From(regional) & " countries; negotiate one regional agreement.",
                Next = "Combine volumes across those countries; run one RFQ/negotiation with " & top
                    & " and 1-2 alternatives; one agreement with country call-offs."]
            else if t = "C" then [Type = "Business-led",
                Action = "Business selects supplier; " & route & ".",
                Next = "Agree panel or engagement terms with the business owner; procurement reviews commercial terms above threshold."]
            else [Type = "New agreement",
                Action = "No agreement anywhere yet: " & route & ".",
                Next = if m[Steps] <> null then m[Steps]
                       else "Run a sourcing event (3 quotes) with " & top & " and alternatives; load the result in Ariba."]
        in r & [Owner = m[Lead]]),
    ActExp = Table.ExpandRecordColumn(Act, "_A", {"Type", "Action", "Next", "Owner"},
        {"Action Type", "Recommended Action", "Practical Next Step", "Owner"}),
    WithOn = Table.AddColumn(ActExp, "On-catalogue/Contract Spend", each
        Nz(Record.FieldOrDefault(OnCellLookup, Key([Country]) & "|" & Key([Commodity]), 0)), type number),
    WithCov = Table.AddColumn(WithOn, "Current Coverage", each
        let tot = [#"Off-catalogue Spend"] + [#"On-catalogue/Contract Spend"]
        in if tot = 0 then 0 else [#"On-catalogue/Contract Spend"] / tot, Percentage.Type),

    // ===== 6. Priority within each country (addressable tiers only) =====
    IsExcluded = (tier as text) => List.Contains({"D", "E"}, Text.Start(tier, 1)),
    Addressable = Table.SelectRows(WithCov, each not IsExcluded([Scope Tier])),
    Excluded = Table.AddColumn(Table.AddColumn(Table.SelectRows(WithCov, each IsExcluded([Scope Tier])),
        "Country Rank", each null, Int64.Type), "Priority", each "Excluded", type text),
    PerCountry = Table.Group(Addressable, {"Country"}, {{"T", (g) =>
        let s = Table.Sort(g, {{"Off-catalogue Spend", Order.Descending}}),
            amts = s[#"Off-catalogue Spend"],
            tot = List.Sum(amts),
            cum = List.Skip(List.Accumulate(amts, {0}, (a, x) => a & {List.Last(a) + x})),
            before = List.Transform(List.Positions(amts), each if tot = 0 then 1 else (cum{_} - amts{_}) / tot),
            pri = List.Transform(before, each if _ < HighCut then "High" else if _ < MediumCut then "Medium" else "Low")
        in Table.FromColumns(Table.ToColumns(s) & {List.Transform(List.Positions(amts), each _ + 1), pri},
            Table.ColumnNames(s) & {"Country Rank", "Priority"})}}),
    Ranked = if Table.IsEmpty(PerCountry) then Excluded
        else Table.Combine(PerCountry[T] & {Excluded}),
    PriorityOrder = (p as text) => List.PositionOf({"High", "Medium", "Low", "Excluded"}, p),
    Sorted = Table.Sort(Table.AddColumn(Ranked, "_p", each PriorityOrder([Priority]), Int64.Type),
        {{"Country", Order.Ascending}, {"_p", Order.Ascending}, {"Off-catalogue Spend", Order.Descending}}),

    Final = Table.SelectColumns(Sorted, {"Country", "Priority", "Country Rank", "Category", "Commodity",
        "Scope Tier", "Action Type", "Recommended Action", "Practical Next Step", "Owner",
        "Off-catalogue Spend", "On-catalogue/Contract Spend", "Current Coverage", "Lines", "Suppliers",
        "Top Supplier", "Top Supplier Share", "Category Route"}),
    Typed = Table.TransformColumnTypes(Final, {
        {"Country", type text}, {"Priority", type text}, {"Country Rank", Int64.Type}, {"Category", type text},
        {"Commodity", type text}, {"Scope Tier", type text}, {"Action Type", type text},
        {"Recommended Action", type text}, {"Practical Next Step", type text}, {"Owner", type text},
        {"Off-catalogue Spend", type number}, {"On-catalogue/Contract Spend", type number},
        {"Current Coverage", Percentage.Type}, {"Lines", type number}, {"Suppliers", Int64.Type},
        {"Top Supplier", type text}, {"Top Supplier Share", Percentage.Type}, {"Category Route", type text}})
in
    Typed

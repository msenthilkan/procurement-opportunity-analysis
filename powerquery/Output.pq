// Output.pq
// Builds one row per requisition line, enriched with taxonomy, buying channel,
// approver classification, country and month. Load this query to a sheet as table "Output".
// Inputs (connection-only queries): qSpend, qApproverRaw, qTaxonomy, qUserMaster, qProcurementGroup
let
    // ===== Settings: change these to match your files =====
    CodeCol  = "Purchasing Commodity number",   // taxonomy commodity number column
    UMName   = "Name",                          // user master: approver name column
    UMEmail  = "Business Email Address",        // user master: email column
    ReqId    = "[REQ] Requisition ID",
    ApprUser = "[APS]Approved by User (User)",

    // ===== Helpers: remove extra spaces; lowercase for matching =====
    Clean = (x as any) as text =>
        if x = null then "" else Text.Combine(List.Select(Text.SplitAny(
            Text.Replace(Text.From(x), Character.FromNumber(160), " "),
            " #(tab)#(cr)#(lf)"), each _ <> ""), " "),
    Key = (x as any) as text => Text.Lower(Clean(x)),
    IdText = (t as table) => Table.TransformColumns(t,
        {{ReqId, each if _ = null then null else Text.From(_), type text}}),
    Names = (t as table) => Text.Combine(List.Sort(List.Distinct(
        List.RemoveNulls(Table.Column(t, ApprUser)))), "; "),

    // ===== Inputs =====
    Spend      = IdText(Table.TransformColumnNames(qSpend, each Clean(_))),
    Approver   = IdText(Table.TransformColumnNames(qApproverRaw, each Clean(_))),
    Taxonomy   = Table.TransformColumnNames(qTaxonomy, each Clean(_)),
    UserMaster = Table.TransformColumnNames(qUserMaster, each Clean(_)),

    // ===== Lookup 1: approver name -> email (active accounts first) =====
    UMRanked = Table.Buffer(Table.Sort(Table.AddColumn(
        Table.SelectRows(UserMaster, each Key(Record.Field(_, UMEmail)) <> ""),
        "_Rank", each if List.Contains({"yes", "true", "1"}, Key([Active])) then 0 else 1,
        Int64.Type), {{"_Rank", Order.Ascending}})),
    EmailLookup = Table.Buffer(Table.Distinct(Table.SelectRows(
        Table.AddColumn(Table.SelectColumns(UMRanked, {UMName, UMEmail}),
            "_NameKey", each Key(Record.Field(_, UMName)), type text),
        each [_NameKey] <> ""), {"_NameKey"})),

    // ===== Lookup 2: procurement group emails =====
    ProcList = List.Buffer(List.Transform(
        Table.TransformColumnNames(qProcurementGroup, each Clean(_))[Email], Key)),

    // ===== Approvers: tag each one, then one row per requisition =====
    Approvals = Table.SelectRows(
        Table.Distinct(Table.SelectColumns(Approver, {ReqId, ApprUser})),
        each Key(Record.Field(_, ApprUser)) <> ""),
    ApprKey = Table.AddColumn(Approvals, "_NameKey",
        each Key(Record.Field(_, ApprUser)), type text),
    ApprJoin = Table.NestedJoin(ApprKey, {"_NameKey"}, EmailLookup, {"_NameKey"},
        "_L", JoinKind.LeftOuter),
    ApprExp = Table.ExpandTableColumn(ApprJoin, "_L", {UMEmail}, {"Email"}),
    ApprTag = Table.AddColumn(ApprExp, "Approver Type", each
        if List.Contains(ProcList, Key([Email])) then "Procurement" else "Business/Finance",
        type text),
    ApprSummary = Table.Group(ApprTag, {ReqId}, {
        {"Approvers", each Names(_), type text},
        {"Approver Emails", each Text.Combine(List.Sort(List.Distinct(
            List.RemoveNulls([Email]))), "; "), type text},
        {"Procurement Approvers", each Names(Table.SelectRows(_,
            each [Approver Type] = "Procurement")), type text},
        {"Business/Finance Approvers", each Names(Table.SelectRows(_,
            each [Approver Type] = "Business/Finance")), type text},
        {"Approvers Not In List", each Names(Table.SelectRows(_,
            each [Email] = null)), type text},
        {"Procurement Involved", each
            if List.Contains([Approver Type], "Procurement") then "Yes" else "No", type text},
        {"Business/Finance Involved", each
            if List.Contains([Approver Type], "Business/Finance") then "Yes" else "No", type text},
        {"Approval Route", each
            let p = List.Contains([Approver Type], "Procurement"),
                b = List.Contains([Approver Type], "Business/Finance")
            in if p and b then "Procurement + Business/Finance"
               else if p then "Procurement only" else "Business/Finance only", type text}
    }),

    // ===== Taxonomy lookup: match short OR long commodity name =====
    Fields = {
        "Level 0 (Group)", "Level 1 (Family)", "Level 2 (Category)",
        "Level 3 (Commodity) - Long", CodeCol,
        "Procurement Or Business Led", "Operating Model Types",
        "Procurement Category Classification", "Execution Strategy"
    },
    Aliases = Table.ExpandListColumn(Table.AddColumn(Taxonomy, "_Key", each List.Distinct({
        Key([#"Level 3 (Commodity) - Short"]), Key([#"Level 3 (Commodity) - Long"])})), "_Key"),
    Mapping = Table.Distinct(Table.SelectColumns(
        Table.SelectRows(Aliases, each [_Key] <> ""), {"_Key"} & Fields, MissingField.UseNull)),
    TaxGrouped = Table.Group(Mapping, {"_Key"}, {{"Value", each
        [Count = Table.RowCount(_), Row = Record.SelectFields(_{0}, Fields)]}}),
    TaxLookup = Record.FromTable(Table.RenameColumns(TaxGrouped, {{"_Key", "Name"}})),

    // ===== Match spend to taxonomy =====
    WithKey = Table.AddColumn(Spend, "_Key", each Key([#"[REQ]Commodity (Commodity (L3))"]), type text),
    WithM = Table.AddColumn(WithKey, "_M", each Record.FieldOrDefault(TaxLookup, [_Key], null)),
    TaxMatch = Table.AddColumn(WithM, "Taxonomy Match", each
        if [_M] = null then (if [_Key] = "" then "Blank" else "Unmapped")
        else if [_M][Count] = 1 then "Matched" else "Ambiguous", type text),
    TaxRec = Table.AddColumn(TaxMatch, "_Tax", each
        if [Taxonomy Match] = "Matched" then [_M][Row] else null),
    TaxCols = Table.ExpandRecordColumn(TaxRec, "_Tax", Fields,
        List.Transform(Fields, each "Taxonomy." & _)),

    // ===== Catalogue and contract flags =====
    Catalogue = Table.AddColumn(TaxCols, "Catalogue Status", each
        let t = Key([#"[REQ] Line Type"]) in
        if t = "catalog item" then "Catalogue"
        else if t = "non-catalog item" then "Non-catalogue" else "Unclassified", type text),
    Contract = Table.AddColumn(Catalogue, "Contract Linked", each
        if List.Contains({"", "null", "n/a", "-", "none"}, Key([#"[REQ]Contract (Contract)"]))
        then "No" else "Yes", type text),

    // ===== One buying channel: Catalogue / Contract / Non-catalogue =====
    Channel = Table.AddColumn(Contract, "Buying Channel", each
        if [Catalogue Status] = "Catalogue" then "Catalogue"
        else if [Contract Linked] = "Yes" then "Contract"
        else if [Catalogue Status] = "Non-catalogue" then "Non-catalogue"
        else "Unclassified", type text),
    ChannelGroup = Table.AddColumn(Channel, "Channel Group", each
        if List.Contains({"Catalogue", "Contract"}, [Buying Channel])
        then "Catalogue + Contract" else [Buying Channel], type text),

    // ===== Add approver details =====
    ApprCols = {"Approvers", "Approver Emails", "Procurement Approvers",
        "Business/Finance Approvers", "Approvers Not In List",
        "Procurement Involved", "Business/Finance Involved", "Approval Route"},
    JoinA = Table.NestedJoin(ChannelGroup, {ReqId}, ApprSummary, {ReqId}, "_A", JoinKind.LeftOuter),
    WithA = Table.ExpandTableColumn(JoinA, "_A", ApprCols),
    NoApproval = Table.ReplaceValue(WithA, null, "No approval data", Replacer.ReplaceValue,
        {"Procurement Involved", "Business/Finance Involved", "Approval Route"}),

    // ===== Taxonomy intent: who SHOULD lead =====
    Intent = Table.AddColumn(NoApproval, "Taxonomy Intent", each
        let v = Key([#"Taxonomy.Procurement Or Business Led"]) in
        if [Taxonomy Match] <> "Matched" then "Unmapped"
        else if Text.Contains(v, "procurement") then "Procurement-led"
        else if Text.Contains(v, "business") then "Business-led" else "Unspecified", type text),

    // ===== Types and month =====
    // Dates: real dates, Excel serial numbers, or source text dates in M/D/YYYY (8/11/2026 = 11 Aug).
    ToDate = (x as any) as nullable date =>
        if x = null then null
        else if x is date then x
        else if x is datetime or x is number then Date.From(x)
        else let t = Text.Trim(Text.From(x)) in
            if t = "" then null
            else try Date.From(t, "en-US") otherwise null,
    Typed = Table.TransformColumns(Intent, {
        {"[REQ]Requisition Date (Date)", ToDate, type nullable date},
        {"[PO-P&I]Ordered Date (Date)", ToDate, type nullable date},
        {"sum(Requisition Spend)", each try Number.From(_) otherwise null, type nullable number},
        {"sum(PO Spend)", each try Number.From(_) otherwise null, type nullable number}}),
    WithMonth = Table.AddColumn(Typed, "Month", each
        if [#"[REQ]Requisition Date (Date)"] = null then null
        else Date.StartOfMonth([#"[REQ]Requisition Date (Date)"]), type nullable date),
    WithPOMonth = Table.AddColumn(WithMonth, "PO Month", each
        if [#"[PO-P&I]Ordered Date (Date)"] = null then null
        else Date.StartOfMonth([#"[PO-P&I]Ordered Date (Date)"]), type nullable date),

    // ===== Country name from purchasing organisation code =====
    // Add a line here when a new country goes live.
    CountryMap = [
        AE01 = "UAE", CA01 = "Canada", DE01 = "Germany", ID01 = "Indonesia",
        JP01 = "Japan", TR01 = "Turkey", US01 = "USA", ZA01 = "South Africa"
    ],
    OrgCol = "[REQ]Purchasing Company (Purchase Organization Id)",
    WithCountry = Table.AddColumn(WithPOMonth, "Country", each
        let v = Record.Field(_, OrgCol),
            code = if v = null then "" else Text.Upper(Text.Trim(Text.From(v)))
        in if code = "" then "Blank"
           else Record.FieldOrDefault(CountryMap, code, code & " (not mapped)"), type text),

    Output = Table.RemoveColumns(WithCountry, {"_Key", "_M"})
in
    Output

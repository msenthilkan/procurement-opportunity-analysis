// qPCardOut.pq
// Turns the card issuer statement into spend lines with the same columns as Output, so the
// two can be appended (qAllSpend). Adds MCC-based categorisation and P-card compliance flags.
// Inputs (connection-only): qPCard (card statement), qMCCMap (MCC -> L3), qTaxonomy. Uses Output.
// Load as connection only.
let
    // ===== Settings: change these to match your card export =====
    SingleLimit = 2500,                                 // single-transaction limit (reporting currency)
    TxnCol      = "Transaction ID",
    DateCol     = "Transaction Date",
    HolderCol   = "Cardholder Name",
    HolderMail  = "Cardholder Email",
    OrgCodeCol  = "Purchase Org",                       // same codes as Ariba purchasing organisation
    MerchantCol = "Merchant Name",
    MccCol      = "MCC",
    AmountCol   = "Amount (Reporting Currency)",
    ReceiptCol  = "Receipt Attached",                   // optional
    PORefCol    = "PO Reference",                       // optional: set when an Ariba PO was paid by card
    CodedCol    = "Commodity (Cardholder Coded)",       // optional: commodity chosen at reconciliation
    CodeCol     = "Purchasing Commodity number",

    // ===== Helpers (same as Output) =====
    Clean = (x as any) as text =>
        if x = null then "" else Text.Combine(List.Select(Text.SplitAny(
            Text.Replace(Text.From(x), Character.FromNumber(160), " "),
            " #(tab)#(cr)#(lf)"), each _ <> ""), " "),
    Key = (x as any) as text => Text.Lower(Clean(x)),
    MccKey = (x as any) as text => if x = null then "" else Text.PadStart(Clean(x), 4, "0"),
    ToDate = (x as any) as nullable date =>
        if x = null then null
        else if x is date then x
        else if x is datetime or x is number then Date.From(x)
        else let t = Text.Trim(Text.From(x)) in
            if t = "" then null else try Date.From(t, "en-US") otherwise null,

    Card     = Table.TransformColumnNames(qPCard, each Clean(_)),
    MccTbl   = Table.TransformColumnNames(qMCCMap, each Clean(_)),
    Taxonomy = Table.TransformColumnNames(qTaxonomy, each Clean(_)),
    OrgCol   = "[REQ]Purchasing Company (Purchase Organization Id)",
    SupCol   = List.First(List.Select(Table.ColumnNames(Output),
                   each Text.StartsWith(_, "[REQ]Supplier")), "[REQ]Supplier (Common Supplier)"),

    // ===== 1. Remove card payments of Ariba POs (already in Output) to avoid double counting =====
    POList = List.Buffer(List.Select(List.Distinct(List.Transform(Output[#"[REQ] PO Id"], Key)),
                 each _ <> "")),
    HasPORef = Table.HasColumns(Card, PORefCol),
    WithPO = Table.AddColumn(Card, "_PO", each if HasPORef then Key(Record.Field(_, PORefCol)) else "", type text),
    OffPlatform = Table.SelectRows(WithPO, each [_PO] = "" or not List.Contains(POList, [_PO])),

    // ===== 2. MCC lookup -> L3 name, description, MCC policy =====
    MccRows = Table.Distinct(Table.SelectRows(Table.AddColumn(MccTbl, "_Mcc", each MccKey([MCC]), type text),
        each [_Mcc] <> ""), {"_Mcc"}),
    MccLookup = Record.FromTable(Table.FromRecords(List.Transform(Table.ToRecords(MccRows), each [
        Name = [_Mcc],
        Value = [Desc = Record.FieldOrDefault(_, "MCC Description", null),
                 L3 = Record.FieldOrDefault(_, "Level 3 (Commodity) - Long", null),
                 Policy = Record.FieldOrDefault(_, "MCC Policy", null)]]))),
    HasCoded = Table.HasColumns(Card, CodedCol),
    WithMcc = Table.AddColumn(OffPlatform, "_Mc", each
        Record.FieldOrDefault(MccLookup, MccKey(Record.Field(_, MccCol)), [Desc = null, L3 = null, Policy = null])),
    // Commodity: cardholder-coded first, then the MCC mapping, then the MCC itself
    WithCommodity = Table.AddColumn(WithMcc, "[REQ]Commodity (Commodity (L3))", each
        let coded = if HasCoded then Clean(Record.Field(_, CodedCol)) else "",
            l3 = Clean([_Mc][L3])
        in if coded <> "" then coded
           else if l3 <> "" then l3
           else "MCC " & MccKey(Record.Field(_, MccCol)) & " " & Clean([_Mc][Desc]), type text),

    // ===== 3. Taxonomy match (same rules as Output) =====
    Fields = {
        "Level 0 (Group)", "Level 1 (Family)", "Level 2 (Category)",
        "Level 3 (Commodity) - Long", CodeCol,
        "Procurement Or Business Led", "Operating Model Types",
        "Procurement Category Classification", "Execution Strategy", "P-card Policy",
        "Scope Tier", "Proposed Route"
    },
    Aliases = Table.ExpandListColumn(Table.AddColumn(Taxonomy, "_Key", each List.Distinct({
        Key([#"Level 3 (Commodity) - Short"]), Key([#"Level 3 (Commodity) - Long"])})), "_Key"),
    Mapping = Table.Distinct(Table.SelectColumns(
        Table.SelectRows(Aliases, each [_Key] <> ""), {"_Key"} & Fields, MissingField.UseNull)),
    TaxGrouped = Table.Group(Mapping, {"_Key"}, {{"Value", each
        [Count = Table.RowCount(_), Row = Record.SelectFields(_{0}, Fields)]}}),
    TaxLookup = Record.FromTable(Table.RenameColumns(TaxGrouped, {{"_Key", "Name"}})),
    WithKey = Table.AddColumn(WithCommodity, "_Key", each Key([#"[REQ]Commodity (Commodity (L3))"]), type text),
    WithM = Table.AddColumn(WithKey, "_M", each Record.FieldOrDefault(TaxLookup, [_Key], null)),
    TaxMatch = Table.AddColumn(WithM, "Taxonomy Match", each
        if [_M] = null then (if [_Key] = "" then "Blank" else "Unmapped")
        else if [_M][Count] = 1 then "Matched" else "Ambiguous", type text),
    TaxRec = Table.AddColumn(TaxMatch, "_Tax", each if [Taxonomy Match] = "Matched" then [_M][Row] else null),
    TaxCols = Table.ExpandRecordColumn(TaxRec, "_Tax", Fields, List.Transform(Fields, each "Taxonomy." & _)),
    Intent = Table.AddColumn(TaxCols, "Taxonomy Intent", each
        let v = Key([#"Taxonomy.Procurement Or Business Led"]) in
        if [Taxonomy Match] <> "Matched" then "Unmapped"
        else if Text.Contains(v, "procurement") then "Procurement-led"
        else if Text.Contains(v, "business") then "Business-led" else "Unspecified", type text),

    // ===== 4. Columns that line up with Output =====
    Base = Table.AddColumn(Intent, "_B", each
        let amt = try Number.From(Record.Field(_, AmountCol)) otherwise null,
            d = ToDate(Record.Field(_, DateCol))
        in [ReqId = "PCARD-" & Clean(Record.Field(_, TxnCol)),
            Supplier = Clean(Record.Field(_, MerchantCol)),
            Org = Clean(Record.Field(_, OrgCodeCol)),
            TxnDate = d, Amount = amt,
            Holder = Clean(Record.Field(_, HolderCol)),
            HolderEmail = Clean(Record.FieldOrDefault(_, HolderMail, null)),
            Mcc = MccKey(Record.Field(_, MccCol)), MccDesc = [_Mc][Desc],
            Receipt = if Table.HasColumns(Card, ReceiptCol) then Key(Record.Field(_, ReceiptCol)) else "yes",
            Policy = let tp = Clean([#"Taxonomy.P-card Policy"]), mp = Clean([_Mc][Policy])
                     in if tp <> "" then tp else if mp <> "" then mp else "Unknown"]),
    BaseExp = Table.ExpandRecordColumn(Base, "_B",
        {"ReqId", "Supplier", "Org", "TxnDate", "Amount", "Holder", "HolderEmail", "Mcc", "MccDesc", "Receipt", "Policy"}),

    // ===== 5. Compliance checks =====
    // Split purchases: same cardholder, merchant and day, together above the single limit
    SplitKeyed = Table.AddColumn(BaseExp, "_Split", each
        Key([Holder]) & "|" & Key([Supplier]) & "|" & (if [TxnDate] = null then "" else Date.ToText([TxnDate], "yyyy-MM-dd")), type text),
    SplitStats = Table.Group(SplitKeyed, {"_Split"}, {{"Value", each
        [N = Table.RowCount(_), Sum = List.Sum([Amount])]}}),
    SplitLookup = Record.FromTable(Table.RenameColumns(SplitStats, {{"_Split", "Name"}})),
    // Suppliers already on catalogue or contract in Ariba (card use there is leakage)
    OnPlatformSup = List.Buffer(List.Distinct(List.Transform(Table.Column(Table.SelectRows(Output,
        each List.Contains({"Catalogue", "Contract"}, [Buying Channel])), SupCol), Key))),
    Flags = Table.AddColumn(SplitKeyed, "P-card Flags", each
        let s = Record.Field(SplitLookup, [_Split]),
            amt = if [Amount] = null then 0 else [Amount],
            f = List.RemoveNulls({
                if [Policy] = "Blocked" then "Blocked category" else null,
                if [Policy] = "Restricted" then "Restricted category" else null,
                if amt > SingleLimit then "Over single limit" else null,
                if s[N] > 1 and s[Sum] > SingleLimit and amt <= SingleLimit then "Possible split" else null,
                if List.Contains(OnPlatformSup, Key([Supplier])) then "Catalogue/contract supplier" else null,
                if not List.Contains({"yes", "y", "true", "1"}, [Receipt]) then "Missing receipt" else null})
        in if List.IsEmpty(f) then "None" else Text.Combine(f, "; "), type text),
    Compliance = Table.AddColumn(Flags, "P-card Compliance", each
        let f = [#"P-card Flags"] in
        if f = "None" then "Compliant"
        else if List.AnyTrue(List.Transform({"Blocked", "Over single", "split", "Catalogue/contract"},
            (k) => Text.Contains(f, k))) then "Non-compliant"
        else "Review", type text),

    // ===== 6. Country from the codes already mapped in Output =====
    CountryPairs = Table.Distinct(Table.SelectColumns(Output, {OrgCol, "Country"}), {OrgCol}),
    CountryLookup = Record.FromTable(Table.RenameColumns(Table.Distinct(Table.TransformColumns(CountryPairs,
        {{OrgCol, each Text.Upper(Clean(_)), type text}}), {OrgCol}), {{OrgCol, "Name"}, {"Country", "Value"}})),

    Final = Table.FromRecords(Table.TransformRows(Compliance, (r) => [
        #"[REQ] Requisition ID" = r[ReqId],
        #"[REQ]Supplier (Common Supplier)" = r[Supplier],
        #"[REQ]Requisition Date (Date)" = r[TxnDate],
        #"[PO-P&I]Ordered Date (Date)" = r[TxnDate],
        #"[REQ]Purchasing Company (Purchase Organization Id)" = r[Org],
        #"[REQ]Commodity (Commodity (L3))" = r[#"[REQ]Commodity (Commodity (L3))"],
        #"[REQ] Line Type" = "P-card transaction",
        #"sum(Line Count)" = 1,
        #"sum(Requisition Spend)" = r[Amount],
        #"sum(PO Spend)" = r[Amount],
        #"Taxonomy Match" = r[Taxonomy Match],
        #"Taxonomy.Level 0 (Group)" = r[#"Taxonomy.Level 0 (Group)"],
        #"Taxonomy.Level 1 (Family)" = r[#"Taxonomy.Level 1 (Family)"],
        #"Taxonomy.Level 2 (Category)" = r[#"Taxonomy.Level 2 (Category)"],
        #"Taxonomy.Level 3 (Commodity) - Long" = r[#"Taxonomy.Level 3 (Commodity) - Long"],
        #"Taxonomy.Procurement Or Business Led" = r[#"Taxonomy.Procurement Or Business Led"],
        #"Taxonomy.Execution Strategy" = r[#"Taxonomy.Execution Strategy"],
        #"Taxonomy.P-card Policy" = r[#"Taxonomy.P-card Policy"],
        #"Taxonomy.Scope Tier" = r[#"Taxonomy.Scope Tier"],
        #"Taxonomy.Proposed Route" = r[#"Taxonomy.Proposed Route"],
        #"Catalogue Status" = "P-card",
        #"Contract Linked" = "No",
        #"Payment Method" = "P-card",
        #"Buying Channel" = "P-card (off-platform)",
        #"Channel Group" = "P-card",
        #"Procurement Involved" = "No",
        #"Business/Finance Involved" = "No",
        #"Approval Route" = "Card (no requisition)",
        #"Taxonomy Intent" = r[Taxonomy Intent],
        Month = if r[TxnDate] = null then null else Date.StartOfMonth(r[TxnDate]),
        #"PO Month" = if r[TxnDate] = null then null else Date.StartOfMonth(r[TxnDate]),
        Country = if r[Org] = "" then "Blank"
                  else Record.FieldOrDefault(CountryLookup, Text.Upper(r[Org]), r[Org] & " (not mapped)"),
        Cardholder = r[Holder],
        #"Cardholder Email" = r[HolderEmail],
        MCC = r[Mcc],
        #"MCC Description" = r[MccDesc],
        #"P-card Policy" = r[Policy],
        #"P-card Flags" = r[#"P-card Flags"],
        #"P-card Compliance" = r[#"P-card Compliance"],
        #"Source System" = "P-card statement"
    ])),
    Typed = Table.TransformColumnTypes(Final, {
        {"[REQ]Requisition Date (Date)", type date}, {"[PO-P&I]Ordered Date (Date)", type date},
        {"Month", type date}, {"PO Month", type date},
        {"sum(Requisition Spend)", type number}, {"sum(PO Spend)", type number}, {"sum(Line Count)", type number}})
in
    Typed

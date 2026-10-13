// qTaxonomyPolicy.pq  (name this query qTaxonomy)
// Adds Scope Tier, Proposed Route and P-card Policy from the scope matrix to every taxonomy row.
// Setup: rename your raw taxonomy query to qTaxonomyRaw; keep the scope matrix as Excel table
// tblScopeMatrix in this workbook (columns "L3 Commodity", "Scope Tier", "Proposed Route", "P-card Policy").
// Matching uses the L3 long name first, then the short name (case and spacing ignored).
let
    Clean = (x as any) as text =>
        if x = null then "" else Text.Combine(List.Select(Text.SplitAny(
            Text.Replace(Text.From(x), Character.FromNumber(160), " "),
            " #(tab)#(cr)#(lf)"), each _ <> ""), " "),
    Key = (x as any) as text => Text.Lower(Clean(x)),
    Added = {"Scope Tier", "Proposed Route", "P-card Policy"},

    Raw = Table.TransformColumnNames(qTaxonomyRaw, each Clean(_)),
    // If the raw taxonomy already has any of these columns, the matrix value replaces it
    RawOnly = Table.RemoveColumns(Raw, List.Intersect({Table.ColumnNames(Raw), Added})),

    Matrix = Table.TransformColumnNames(
        Excel.CurrentWorkbook(){[Name = "tblScopeMatrix"]}[Content], each Clean(_)),
    Keyed = Table.SelectRows(Table.AddColumn(Matrix, "_k", each Key([L3 Commodity]), type text),
        each [_k] <> ""),
    Unique = Table.Distinct(Keyed, {"_k"}),
    Lookup = Record.FromTable(Table.FromRecords(List.Transform(Table.ToRecords(Unique), each
        [Name = [_k], Value = Record.SelectFields(_, Added, MissingField.UseNull)]))),
    Empty = Record.FromList({null, null, null}, Added),

    Matched = Table.AddColumn(RawOnly, "_s", each
        let long = Record.FieldOrDefault(Lookup, Key(Record.FieldOrDefault(_, "Level 3 (Commodity) - Long", null)), null),
            short = Record.FieldOrDefault(Lookup, Key(Record.FieldOrDefault(_, "Level 3 (Commodity) - Short", null)), null)
        in if long <> null then long else if short <> null then short else Empty),
    Expanded = Table.ExpandRecordColumn(Matched, "_s", Added)
in
    Expanded

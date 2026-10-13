// qTaxonomyPolicy.pq  (name this query qTaxonomy)
// Adds Scope Tier, Proposed Route and (if present) P-card Policy from the scope matrix to every
// taxonomy row. Setup: rename your raw taxonomy query to qTaxonomyRaw, and load the scope matrix
// table as a connection-only query named tblScopeMatrix (Data > From Table/Range, or From Workbook
// for a separate file). The matrix is read through that query, not Excel.CurrentWorkbook(), because
// combining another query with a direct data source triggers Power Query's Formula.Firewall error.
// Matching uses the L3 long name first, then the short name (case and spacing ignored).
// Only columns the matrix actually has are replaced; other taxonomy columns are kept as they are.
let
    Clean = (x as any) as text =>
        if x = null then "" else Text.Combine(List.Select(Text.SplitAny(
            Text.Replace(Text.From(x), Character.FromNumber(160), " "),
            " #(tab)#(cr)#(lf)"), each _ <> ""), " "),
    Key = (x as any) as text => Text.Lower(Clean(x)),
    Wanted = {"Scope Tier", "Proposed Route", "P-card Policy"},

    // ----- scope matrix (accepts older header names too)
    MatrixIn = Table.TransformColumnNames(tblScopeMatrix, each Clean(_)),
    MatrixRaw = Table.RenameColumns(MatrixIn, List.Select(
        {{"Proposed Scope Tier", "Scope Tier"}, {"Proposed Execution", "Proposed Route"}},
        each List.Contains(Table.ColumnNames(MatrixIn), _{0})
            and not List.Contains(Table.ColumnNames(MatrixIn), _{1}))),
    L3Col = List.First(List.Select({"L3 Commodity", "L3 Scope Matrix", "L3 Long", "L3", "Commodity"},
        each List.Contains(Table.ColumnNames(MatrixRaw), _)), null),
    Matrix = if L3Col = null
        or not List.ContainsAll(Table.ColumnNames(MatrixRaw), {"Scope Tier", "Proposed Route"})
        then error Error.Record("tblScopeMatrix is missing columns",
            "It needs an L3 column (L3 Commodity) plus Scope Tier and Proposed Route. " &
            "Columns found: " & Text.Combine(Table.ColumnNames(MatrixRaw), ", "))
        else MatrixRaw,
    Added = List.Select(Wanted, each List.Contains(Table.ColumnNames(Matrix), _)),
    Keyed = Table.SelectRows(Table.AddColumn(Matrix, "_k", each Key(Record.Field(_, L3Col)), type text),
        each [_k] <> ""),
    Unique = Table.Distinct(Keyed, {"_k"}),
    Lookup = Record.FromTable(Table.FromRecords(List.Transform(Table.ToRecords(Unique), each
        [Name = [_k], Value = Record.SelectFields(_, Added)]))),
    Empty = Record.FromList(List.Repeat({null}, List.Count(Added)), Added),

    // ----- taxonomy: drop only the columns the matrix replaces
    Raw = Table.TransformColumnNames(qTaxonomyRaw, each Clean(_)),
    RawOnly = Table.RemoveColumns(Raw, List.Intersect({Table.ColumnNames(Raw), Added})),
    Matched = Table.AddColumn(RawOnly, "_s", each
        let long = Record.FieldOrDefault(Lookup, Key(Record.FieldOrDefault(_, "Level 3 (Commodity) - Long", null)), null),
            short = Record.FieldOrDefault(Lookup, Key(Record.FieldOrDefault(_, "Level 3 (Commodity) - Short", null)), null)
        in if long <> null then long else if short <> null then short else Empty),
    Expanded = Table.ExpandRecordColumn(Matched, "_s", Added)
in
    Expanded

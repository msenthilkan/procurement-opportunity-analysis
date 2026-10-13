// qAllSpend.pq
// One spend table for the dashboard and qOpportunities.
// Default: Ariba requisitions only (Output).
// P-card (optional): if your company has a card programme and you load the card statement
// through qPCardOut, change the "Combined" line to:
//     Combined = Table.Combine({Output, qPCardOut}),
// Card payments of Ariba POs are removed in qPCardOut, so nothing is counted twice.
// Load this query to a sheet as table "AllSpend" and build the pivots on it.
let
    Combined = Output,
    // Card columns always exist (blank without card data), so later queries never break
    CardCols = {"P-card Flags", "P-card Compliance", "P-card Policy"},
    WithCols = List.Accumulate(CardCols, Combined, (t, c) =>
        if Table.HasColumns(t, c) then t else Table.AddColumn(t, c, each null, type text)),
    Filled = Table.ReplaceValue(WithCols, null, "n/a (requisition)", Replacer.ReplaceValue,
        {"P-card Flags", "P-card Compliance"})
in
    Filled

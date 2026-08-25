// STARTEND AGENT BUS V0 — n8n Code node "Prune Bus" (runOnceForAllItems).
//
// Runs after the webhook has already responded, so retention never delays a
// write. Emits one item per row to delete; an empty return means nothing to do
// and the delete node simply does not run.
//
// The old intake kept 5 rows, which is why it could not carry a bus. The floor
// in the brief is 300.

const KEEP = 500;

const rows = $('Read For Prune').all()
  .map((item) => item.json)
  .filter((row) => row && row.id != null)
  .sort((a, b) => (parseInt(b.id, 10) || 0) - (parseInt(a.id, 10) || 0));

return rows.slice(KEEP).map((row) => ({ json: { id: row.id } }));

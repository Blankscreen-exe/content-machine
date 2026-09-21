// Paging and column sorting for the lists, with DataTables.
//
// A table opts in with `data-table` and an id. The server still decides what is in the
// list and its default order (filters, due dates, priority); DataTables only pages it and
// lets a header click re-sort it. It has no search box of its own: the lists already have
// filters, and the ideas search looks inside fields the table does not show.
//
// htmx redraws a list after every change. stateSave keeps the page, page length and sort
// across those redraws, so changing a stage on page 3 leaves you on page 3.
(function () {
  const OPTIONS = {
    order: [],                       // keep the order the server sent until a header is clicked
    pageLength: 25,
    lengthMenu: [10, 25, 50, 100],
    searching: false,
    stateSave: true,
    autoWidth: false,                // widths come from the stylesheet, not measured once
    columnDefs: [
      { targets: "no-sort", orderable: false },
      // Cells sort by text, or by a data-order written to sort as text (ISO dates, single
      // digits). Saying so stops DataTables guessing number and date columns, which it
      // would also right-align, over the alignment the lists already have.
      { targets: "_all", type: "string" },
    ],
    language: {
      lengthMenu: "_MENU_ per page",
      info: "_START_–_END_ of _TOTAL_",
      infoEmpty: "Nothing to show",
      emptyTable: "Nothing here yet.",
    },
  };

  const instances = new WeakMap();

  function enhance(root) {
    const tables = root.matches?.("table[data-table]")
      ? [root]
      : root.querySelectorAll?.("table[data-table]") || [];
    for (const table of tables) {
      if (instances.has(table) || typeof DataTable === "undefined") continue;
      try {
        instances.set(table, new DataTable(table, OPTIONS));
      } catch (error) {
        // An unpaged list is still a working list.
        console.error("paging unavailable for", table.id, error);
      }
    }
  }

  // htmx calls this for the page and for everything it swaps in, after it has wired up
  // the new content's own hx- attributes. Rows on later pages are taken out of the page
  // by DataTables, so they must be wired up first, which this order guarantees.
  htmx.onLoad(enhance);

  // A redraw replaces the table; let go of the old one so it is not kept alive.
  document.body.addEventListener("htmx:beforeCleanupElement", (event) => {
    const instance = instances.get(event.target);
    if (instance) {
      instance.destroy();
      instances.delete(event.target);
    }
  });
})();

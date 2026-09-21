// How long the draft is once pasted, against the piece type's limit.
//
// The count is of the plain text "Copy as plain text" produces (plain_text.js), since that is
// what a platform like LinkedIn receives. The limit comes from the piece type, set under
// Manage; with none set, the count is shown on its own.
(function () {
  function update() {
    const textarea = document.getElementById("draft-text");
    const counter = document.querySelector("#editor-pane .char-count");
    if (!textarea || !counter) return;

    const length = window.contentMachine.plainText(textarea.value).length;
    const limit = Number(counter.dataset.limit) || 0;
    counter.textContent = limit
      ? `${length.toLocaleString()} / ${limit.toLocaleString()} characters`
      : `${length.toLocaleString()} characters`;
    counter.classList.toggle("over-limit", limit > 0 && length > limit);
  }

  document.addEventListener("input", (event) => {
    if (event.target.id === "draft-text") update();
  });
  document.body.addEventListener("htmx:afterSwap", update);
  document.addEventListener("DOMContentLoaded", update);
})();

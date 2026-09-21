// Not losing what you typed.
//
// The draft is unsaved when the textarea holds something other than what the server sent
// (its defaultValue), or when the server refused the last save as a conflict and sent the
// typed text back marked data-unsaved. While it is unsaved:
//
//   - an "unsaved" marker shows next to Save,
//   - leaving the page asks first (the browser's own prompt),
//   - switching to another file, or reloading the saved version, asks first,
//   - Ctrl+S (Cmd+S on a Mac) saves instead of saving the web page.
(function () {
  function draft() {
    return document.getElementById("draft-text");
  }

  function isUnsaved() {
    const textarea = draft();
    if (!textarea || textarea.readOnly) return false;
    return textarea.value !== textarea.defaultValue || textarea.dataset.unsaved === "true";
  }

  function showMarker() {
    const marker = document.querySelector("#editor-pane .unsaved-marker");
    if (marker) marker.hidden = !isUnsaved();
  }

  // editor.js reports every change as an input event on the textarea, as typing into the
  // plain textarea does, so both reach this.
  document.addEventListener("input", (event) => {
    if (event.target === draft()) showMarker();
  });
  document.body.addEventListener("htmx:afterSwap", showMarker);
  document.addEventListener("DOMContentLoaded", showMarker);

  window.addEventListener("beforeunload", (event) => {
    if (isUnsaved()) event.preventDefault();
  });

  // A request that replaces the pane without saving it would throw the typing away.
  document.body.addEventListener("htmx:confirm", (event) => {
    const { elt, target, verb } = event.detail;
    const replacesPane = target && target.id === "editor-pane";
    const isSave = verb === "post" && elt.closest("#editor-pane form");
    if (replacesPane && !isSave && isUnsaved()
        && !window.confirm("Your changes to this draft are not saved. Discard them?")) {
      event.preventDefault();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "s") return;
    const textarea = draft();
    if (!textarea || textarea.readOnly) return;
    event.preventDefault();
    textarea.form.requestSubmit();
  }, true);   // capture: before the editor's own key handling
})();

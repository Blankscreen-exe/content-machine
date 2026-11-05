// Short forms that open over the page, in the browser's own <dialog>.
//
// A button loads a form into the dialog with htmx (hx-get, hx-target="#modal-body"), and the
// dialog opens once it has arrived. The form saves as any htmx form does, redrawing something
// outside the dialog, such as a list; a save that succeeds closes it. Esc, the ✕ and Cancel
// close it without saving. A refused save leaves it open with the reason shown inside it
// (errors.js), so nothing typed is lost.
//
// The browser's showModal() brings the backdrop, Esc, and keeping focus inside the dialog,
// which is why this is a <dialog> and not a styled box.
(function () {
  function dialog() {
    return document.getElementById("modal");
  }

  document.body.addEventListener("htmx:afterSwap", (event) => {
    const modal = dialog();
    if (!modal || event.detail.target.id !== "modal-body") return;
    modal.querySelector(".error-banner").hidden = true;
    if (!modal.open) modal.showModal();
    modal.querySelector("[autofocus]")?.focus();
  });

  document.body.addEventListener("htmx:afterRequest", (event) => {
    const modal = dialog();
    const { elt, target, successful } = event.detail;
    if (modal?.open && successful && modal.contains(elt) && target && !modal.contains(target)) {
      modal.close();
    }
  });

  document.addEventListener("click", (event) => {
    if (event.target.closest("[data-close-modal]")) dialog()?.close();
  });

  document.addEventListener("DOMContentLoaded", () => {
    // emptied on closing, so the next one never shows a moment of the last one's form
    dialog()?.addEventListener("close", () => {
      document.getElementById("modal-body").replaceChildren();
    });
  });
})();

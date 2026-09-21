// Copy the draft to the clipboard, as markdown or as plain text (see plain_text.js).
//
// The clipboard API only exists on https or localhost. Opened from another device on the
// local network (`cm serve --lan`), the page is plain http, so copying falls back to the
// older select-and-copy command, which browsers still support for exactly this case.
(function () {
  function copyBySelection(text) {
    const holder = document.createElement("textarea");
    holder.value = text;
    holder.setAttribute("readonly", "");
    holder.style.position = "fixed";
    holder.style.opacity = "0";
    document.body.appendChild(holder);
    holder.select();
    const copied = document.execCommand("copy");
    holder.remove();
    if (!copied) throw new Error("copy refused");
  }

  async function copy(text, button) {
    const original = button.textContent;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        copyBySelection(text);
      }
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy failed";
    }
    setTimeout(() => { button.textContent = original; }, 1500);
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    const draft = document.getElementById("draft-text");
    if (!draft) return;
    const text = button.dataset.copy === "plain" ? window.contentMachine.plainText(draft.value) : draft.value;
    copy(text, button);
  });
})();

// Toast UI Editor on top of the draft textarea.
//
// The textarea stays in the form and stays the thing that gets submitted; the editor just
// keeps it up to date. So saving, the fingerprint check and the conflict handling work
// exactly as they do without JavaScript, and a failure here degrades to a plain textarea.
(function () {
  let current = null;

  function pasteImage(pieceId) {
    // Toast UI hands us the pasted or dropped file and expects a URL back.
    return async function (blob, callback) {
      const body = new FormData();
      body.append("file", blob, blob.name || "pasted.png");
      try {
        const response = await fetch(`/pieces/${pieceId}/assets`, { method: "POST", body });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "upload failed");
        // The markdown keeps the relative path; the renderer below resolves it for display.
        callback(result.path, blob.name || "image");
      } catch (error) {
        window.alert(`Could not save that image: ${error.message}`);
      }
    };
  }

  function resolveImages(pieceId) {
    return {
      image(node, context) {
        const { destination, firstChild } = node;
        const source = destination.startsWith("assets/")
          ? `/pieces/${pieceId}/assets/${destination.slice("assets/".length)}`
          : destination;
        return {
          type: context.entering ? "openTag" : "closeTag",
          tagName: "img",
          selfClose: true,
          attributes: { src: source, alt: firstChild ? firstChild.literal || "" : "" },
        };
      },
    };
  }

  function mount() {
    const textarea = document.getElementById("draft-text");
    if (!textarea || textarea.dataset.mounted || typeof toastui === "undefined") return;
    if (textarea.hasAttribute("readonly")) return;      // generated files stay plain

    const pieceId = textarea.dataset.pieceId;
    const holder = document.createElement("div");
    textarea.parentNode.insertBefore(holder, textarea);

    try {
      current = new toastui.Editor({
        el: holder,
        height: "560px",
        initialEditType: "markdown",   // toggle to WYSIWYG with the tabs in the editor
        previewStyle: "tab",
        usageStatistics: false,        // nothing phones home
        initialValue: textarea.value,
        hooks: { addImageBlobHook: pasteImage(pieceId) },
        customHTMLRenderer: resolveImages(pieceId),
      });
    } catch (error) {
      // Leave the textarea in place: a plain editor beats no editor.
      holder.remove();
      console.error("rich editor unavailable, using the plain textarea", error);
      return;
    }

    textarea.hidden = true;            // only once the editor is really there
    textarea.dataset.mounted = "true";
    current.on("change", () => { textarea.value = current.getMarkdown(); });
  }

  document.addEventListener("DOMContentLoaded", mount);
  // htmx replaces the whole pane when you switch files or save, so mount again afterwards.
  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.target.id === "editor-pane" || event.target.querySelector?.("#draft-text")) {
      current = null;
      mount();
    }
  });
})();

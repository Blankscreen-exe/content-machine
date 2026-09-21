// Make failed requests visible.
//
// htmx does nothing with an error response by default, so a save that fails looks exactly
// like a save that never happened. This puts the failure in front of you instead, and says
// what to do about it.
(function () {
  const REASONS = {
    403: "The app no longer recognises this tab. Reopen it with the link that `cm serve` prints.",
    404: "That item no longer exists. It may have been deleted in another tab.",
    413: "That was too large to send.",
  };

  function show(text) {
    const banner = document.getElementById("error-banner");
    if (!banner) return;
    banner.querySelector(".error-text").textContent = text;
    banner.hidden = false;
  }

  document.addEventListener("DOMContentLoaded", () => {
    const banner = document.getElementById("error-banner");
    banner?.querySelector(".error-close")?.addEventListener("click", () => { banner.hidden = true; });
  });

  // For anything not covered above, the server's own explanation, which FastAPI sends as
  // {"detail": "..."}, says more than a generic line could.
  function detail(xhr) {
    try {
      const body = JSON.parse(xhr.responseText);
      return typeof body.detail === "string" ? body.detail : null;
    } catch {
      return null;
    }
  }

  document.body.addEventListener("htmx:responseError", (event) => {
    const xhr = event.detail.xhr;
    const reason = REASONS[xhr.status] || detail(xhr) || "The server could not complete that.";
    show(`Nothing was saved (${xhr.status}). ${reason} Your text is still on this page.`);
  });

  document.body.addEventListener("htmx:sendError", () => {
    show("Could not reach the app. Is `cm serve` still running? Your text is still on this page.");
  });
})();

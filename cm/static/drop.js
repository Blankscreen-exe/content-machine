// Dropping files onto the Assets panel, and showing how far an upload has got.
//
// The panel is an ordinary htmx form with a file input; this only lets files be dropped
// onto it instead of picked, and fills in the progress bar, which matters for a large
// Photoshop file sent over the local network.
(function () {
  function zoneOf(event) {
    return event.target.closest?.("[data-drop-zone]");
  }

  document.addEventListener("dragover", (event) => {
    const zone = zoneOf(event);
    if (!zone) return;
    event.preventDefault();                       // allow dropping here
    zone.classList.add("dragging");
  });

  document.addEventListener("dragleave", (event) => {
    zoneOf(event)?.classList.remove("dragging");
  });

  document.addEventListener("drop", (event) => {
    const zone = zoneOf(event);
    if (!zone) return;
    event.preventDefault();
    zone.classList.remove("dragging");
    if (!event.dataTransfer.files.length) return;
    zone.querySelector("input[type=file]").files = event.dataTransfer.files;
    zone.requestSubmit();
  });

  document.body.addEventListener("htmx:xhr:progress", (event) => {
    const zone = event.target.closest?.("[data-drop-zone]");
    const bar = zone?.querySelector("progress");
    if (!bar || !event.detail.lengthComputable) return;
    bar.hidden = false;
    bar.value = Math.round((event.detail.loaded / event.detail.total) * 100);
  });
})();

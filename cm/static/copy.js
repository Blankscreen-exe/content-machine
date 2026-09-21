// Copy the draft to the clipboard, as markdown or as plain text.
//
// LinkedIn and X show markdown as literal characters, so posting there needs the
// syntax removed rather than rendered.
(function () {
  function stripMarkdown(markdown) {
    return markdown
      .replace(/^---\n[\s\S]*?\n---\n/, "")          // frontmatter
      .replace(/^#{1,6}\s+/gm, "")                    // headings
      .replace(/^\s{0,3}>\s?/gm, "")                  // block quotes
      .replace(/```[\s\S]*?```/g, (block) => block.replace(/```\w*\n?/g, ""))
      .replace(/!\[[^\]]*\]\([^)]*\)/g, "")           // images: nothing to paste
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1 ($2)") // links: keep the address
      .replace(/(\*\*|__)(.*?)\1/g, "$2")             // bold
      .replace(/(\*|_)(.*?)\1/g, "$2")                // italic
      .replace(/`([^`]+)`/g, "$1")                    // inline code
      .replace(/^\s*[-*+]\s+/gm, "• ")                // bullets survive as a character
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  async function copy(text, button) {
    const original = button.textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
    } catch {
      button.textContent = "Copy failed";          // clipboard needs a secure context
    }
    setTimeout(() => { button.textContent = original; }, 1500);
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    const draft = document.getElementById("draft-text");
    if (!draft) return;
    copy(button.dataset.copy === "plain" ? stripMarkdown(draft.value) : draft.value, button);
  });
})();

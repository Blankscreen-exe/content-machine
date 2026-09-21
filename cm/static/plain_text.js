// Markdown as it reads once pasted somewhere that does not render it.
//
// LinkedIn and X show markdown as literal characters, so posting there needs the syntax
// removed rather than rendered. Copying as plain text and counting characters both use
// this, so the count is the length of exactly what gets pasted.
(function () {
  function plainText(markdown) {
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

  window.contentMachine = Object.assign(window.contentMachine || {}, { plainText });
})();

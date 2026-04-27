document.addEventListener("DOMContentLoaded", function () {
  const codeBlocks = document.querySelectorAll("pre > code");
  codeBlocks.forEach((code) => {
    const text = code.innerText.trim();
    if (
      text.startsWith("graph") ||
      text.startsWith("flowchart") ||
      text.startsWith("sequenceDiagram") ||
      text.startsWith("erDiagram") ||
      text.startsWith("classDiagram")
    ) {
      const pre = code.parentElement;
      const container = document.createElement("div");
      container.className = "mermaid";
      container.textContent = text;
      pre.parentElement.replaceChild(container, pre);
    }
  });

  if (typeof mermaid !== "undefined") {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'neutral',
      er: {
        useMaxWidth: true,
      }
    });
    mermaid.contentLoaded();
  }
});

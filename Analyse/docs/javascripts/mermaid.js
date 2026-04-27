document.addEventListener("DOMContentLoaded", function () {
  // Fix for auto-detection if MkDocs didn't add the .mermaid class
  const codeBlocks = document.querySelectorAll("pre > code");
  codeBlocks.forEach((code) => {
    const text = code.innerText.trim();
    if (
      text.startsWith("graph") ||
      text.startsWith("flowchart") ||
      text.startsWith("sequenceDiagram") ||
      text.startsWith("erDiagram") ||
      text.startsWith("classDiagram") ||
      text.startsWith("stateDiagram") ||
      text.startsWith("gantt") ||
      text.startsWith("pie")
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
      theme: "base",
      themeVariables: {
        primaryColor: "#673ab7",
        primaryTextColor: "#ffffff",
        primaryBorderColor: "#512da8",
        lineColor: "#673ab7",
        secondaryColor: "#9c27b0",
        tertiaryColor: "#f3e5f5",
        mainBkg: "#673ab7",
        nodeBorder: "#512da8",
        clusterBkg: "#f3e5f5",
        // Spécifique ER Diagram
        attributeFill: "#f8f9fa",
        attributeColor: "#333333",
        entityBkg: "#673ab7",
        entityBorder: "#512da8",
      },
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: "cardinal"
      },
      sequence: {
        useMaxWidth: true,
        actorMargin: 50,
        showSequenceNumbers: false,
      },
      er: {
        useMaxWidth: true,
        layoutDirection: "TB",
      }
    });

    // Manual re-render if needed after DOM manipulation
    mermaid.contentLoaded();
  }
});

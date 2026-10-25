import type { Tool } from "./types.js";
import { stripTags } from "./html.js";

const UA =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

/** Decode DuckDuckGo's redirect links (//duckduckgo.com/l/?uddg=...) to the real URL. */
function resolveDdgLink(href: string): string {
  const m = href.match(/[?&]uddg=([^&]+)/);
  if (m) {
    try {
      return decodeURIComponent(m[1]);
    } catch {
      return href;
    }
  }
  return href.startsWith("//") ? "https:" + href : href;
}

export const webSearchTool: Tool = {
  schema: {
    name: "web_search",
    description:
      "Search the web and return the top results (title, URL, snippet). Use this to look up documentation, errors, library usage, or anything not in the local project. Follow up with fetch_url to read a result in full.",
    parameters: {
      type: "object",
      properties: {
        query: { type: "string", description: "The search query." },
      },
      required: ["query"],
    },
  },
  async execute(args) {
    const query = String(args.query ?? "").trim();
    if (!query) return "Error: empty query.";

    const url = "https://html.duckduckgo.com/html/?q=" + encodeURIComponent(query);
    let html: string;
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": UA, Accept: "text/html" },
      });
      if (!res.ok) return `Error: web search failed (HTTP ${res.status}).`;
      html = await res.text();
    } catch (e) {
      return `Error: web search unavailable (${(e as Error).message}). Network access may be restricted.`;
    }

    // Parse result anchors and their snippets from the HTML results page.
    const results: { title: string; url: string; snippet: string }[] = [];
    const anchorRe = /<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)<\/a>/g;
    const snippetRe = /<a[^>]*class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;

    const snippets: string[] = [];
    let sm: RegExpExecArray | null;
    while ((sm = snippetRe.exec(html))) snippets.push(stripTags(sm[1]));

    let am: RegExpExecArray | null;
    let i = 0;
    while ((am = anchorRe.exec(html)) && results.length < 8) {
      results.push({
        title: stripTags(am[2]),
        url: resolveDdgLink(am[1]),
        snippet: snippets[i] ?? "",
      });
      i++;
    }

    if (!results.length) return `No web results for "${query}".`;
    return results
      .map((r, n) => `${n + 1}. ${r.title}\n   ${r.url}\n   ${r.snippet}`)
      .join("\n\n");
  },
};

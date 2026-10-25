import type { Tool } from "./types.js";
import { htmlToText } from "./html.js";

const UA =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";
const MAX_CHARS = 12000;

export const fetchUrlTool: Tool = {
  schema: {
    name: "fetch_url",
    description:
      "Fetch a URL and return its readable text content (HTML is converted to text). Use this to read documentation pages, articles, or raw files referenced by a web_search result or by the user.",
    parameters: {
      type: "object",
      properties: {
        url: { type: "string", description: "The absolute URL to fetch (http/https)." },
      },
      required: ["url"],
    },
  },
  async execute(args) {
    let url = String(args.url ?? "").trim();
    if (!url) return "Error: empty url.";
    if (!/^https?:\/\//i.test(url)) url = "https://" + url;

    let res: Response;
    try {
      res = await fetch(url, { headers: { "User-Agent": UA }, redirect: "follow" });
    } catch (e) {
      return `Error: could not fetch ${url} (${(e as Error).message}). Network access may be restricted.`;
    }
    if (!res.ok) return `Error: ${url} returned HTTP ${res.status}.`;

    const contentType = res.headers.get("content-type") ?? "";
    const body = await res.text();
    const text = /html/i.test(contentType) ? htmlToText(body) : body;

    if (text.length <= MAX_CHARS) return text;
    return text.slice(0, MAX_CHARS) + `\n\n... (truncated, ${text.length} chars total)`;
  },
};

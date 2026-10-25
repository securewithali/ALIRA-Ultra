/** Minimal HTML helpers shared by web_search and fetch_url (no dependency). */

const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
  "&#x27;": "'",
  "&nbsp;": " ",
};

export function decodeEntities(s: string): string {
  return s
    .replace(/&amp;|&lt;|&gt;|&quot;|&#39;|&#x27;|&nbsp;/g, (m) => ENTITIES[m] ?? m)
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
}

/** Strip tags and collapse whitespace; decode entities. */
export function stripTags(html: string): string {
  return decodeEntities(
    html
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim(),
  );
}

/** Convert a full HTML document to readable plain text. */
export function htmlToText(html: string): string {
  const withoutNoise = html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/<!--[\s\S]*?-->/g, " ")
    // Turn block boundaries into newlines so structure survives.
    .replace(/<\/(p|div|section|article|li|h[1-6]|tr|br)[^>]*>/gi, "\n")
    .replace(/<br\s*\/?>(?=)/gi, "\n");
  return decodeEntities(
    withoutNoise
      .replace(/<[^>]+>/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .split("\n")
      .map((l) => l.trim())
      .join("\n")
      .trim(),
  );
}

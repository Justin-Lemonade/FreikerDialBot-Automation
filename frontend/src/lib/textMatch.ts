/** Splits `text` into [unmatched, matched, unmatched, ...] segments
 * around every case-insensitive occurrence of `query`, so the caller
 * can render matched spans differently. Mirrors the backend's own
 * match logic (Database.search_customers uses a plain `LIKE %query%`
 * substring check, case-insensitive in SQLite for ASCII) -- this never
 * invents match metadata the backend didn't actually use, it just
 * re-runs the same substring test client-side to know where to
 * highlight. Used by Search.tsx's HighlightedText. */
export const splitOnMatch = (text: string, query: string): { text: string; isMatch: boolean }[] => {
  if (!query || !text) return [{ text, isMatch: false }];
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const segments: { text: string; isMatch: boolean }[] = [];
  let cursor = 0;
  while (cursor < text.length) {
    const matchIndex = lowerText.indexOf(lowerQuery, cursor);
    if (matchIndex === -1) {
      segments.push({ text: text.slice(cursor), isMatch: false });
      break;
    }
    if (matchIndex > cursor) {
      segments.push({ text: text.slice(cursor, matchIndex), isMatch: false });
    }
    segments.push({ text: text.slice(matchIndex, matchIndex + query.length), isMatch: true });
    cursor = matchIndex + query.length;
  }
  return segments;
};

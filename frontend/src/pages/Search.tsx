import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Customer } from '../types';

interface Props {
  onSelectCustomer: (customer: Customer) => void;
  /** Pre-fills and immediately runs a search -- used by Commands'
   * typed "search <query>" command so it actually performs the search
   * instead of just opening an empty Search screen. */
  initialQuery?: string;
}

/** Splits `text` into [unmatched, matched, unmatched, ...] segments
 * around every case-insensitive occurrence of `query`, so the caller
 * can render matched spans differently. Mirrors the backend's own
 * match logic (Database.search_customers uses a plain `LIKE %query%`
 * substring check, case-insensitive in SQLite for ASCII) -- this never
 * invents match metadata the backend didn't actually use, it just
 * re-runs the same substring test client-side to know where to
 * highlight. */
const splitOnMatch = (text: string, query: string): { text: string; isMatch: boolean }[] => {
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

const HighlightedText = ({ text, query }: { text: string; query: string }) => (
  <>
    {splitOnMatch(text, query).map((segment, index) =>
      segment.isMatch ? (
        <mark key={index} style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)' }}>
          {segment.text}
        </mark>
      ) : (
        <span key={index}>{segment.text}</span>
      )
    )}
  </>
);

/**
 * Wraps the existing, already-tested GET /customer/search endpoint
 * (Database.search_customers -- matches loan number, name, full name,
 * and phone substring). No new backend surface here, just a Mini App
 * page for a capability that previously only existed via Telegram's
 * /customer command.
 */
export const Search = ({ onSelectCustomer, initialQuery }: Props) => {
  const [query, setQuery] = useState(initialQuery ?? '');
  const [matchedQuery, setMatchedQuery] = useState('');
  const [results, setResults] = useState<Customer[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const runSearch = async (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setResults([]);
      setHasSearched(false);
      return;
    }
    setIsSearching(true);
    setError(null);
    try {
      const { results: found } = await api.searchCustomers(trimmed);
      setResults(found);
      setMatchedQuery(trimmed);
      setHasSearched(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  // Runs once, only when Commands' "search <query>" actually supplied
  // something -- a plain nav-tab visit to Search has no initialQuery
  // and stays empty/interactive as before. Read from a ref (captured
  // once) rather than depending on the prop directly: this is
  // deliberately mount-only, not "re-run whenever initialQuery
  // changes" (a parent re-render with the same prop value shouldn't
  // re-trigger a fresh network request).
  const initialQueryRef = useRef(initialQuery);
  useEffect(() => {
    const value = initialQueryRef.current;
    if (value && value.trim()) {
      runSearch(value);
    }
  }, []);

  return (
    <div className="space-y-4">
      <div className="retro-panel p-4">
        <p className="mb-3 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          FIND THE CLIENT'S
        </p>
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') runSearch(query);
          }}
          onFocus={() => {
            // Mobile browsers resize the visual viewport when the
            // keyboard opens; give that animation a moment, then make
            // sure this input (and the results that will appear below
            // it) stay scrolled into the visible area instead of
            // ending up hidden behind the keyboard.
            window.setTimeout(() => {
              inputRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
            }, 300);
          }}
          placeholder="Name, loan number, or phone"
          inputMode="search"
          enterKeyHint="search"
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          className="min-h-[48px] w-full px-4 font-data text-lg outline-none"
          style={{ background: 'var(--bg-panel)', border: '1px solid var(--border-frame)', color: 'var(--text-primary)' }}
        />
        <button
          onClick={() => runSearch(query)}
          disabled={isSearching}
          className="retro-button mt-3 min-h-[48px] w-full font-display text-xs disabled:opacity-60"
          style={{ background: 'var(--accent-green)', color: 'var(--accent-green-text)', border: '2px solid var(--accent-green-strong)' }}
        >
          {isSearching ? 'SEARCHING…' : '🔍 SEARCH'}
        </button>
      </div>

      {error && (
        <div className="p-4 text-center font-data text-lg" style={{ border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
          {error}
        </div>
      )}

      {hasSearched && !error && results.length === 0 && (
        <div className="retro-panel p-4 text-center font-data text-lg" style={{ color: 'var(--text-muted)' }}>
          No customers found matching "{query}".
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-2.5">
          {results.map((customer) => (
            <button
              key={customer.id}
              onClick={() => onSelectCustomer(customer)}
              className="retro-card retro-button w-full px-4 py-3 text-left"
            >
              <p className="break-words font-data text-xl" style={{ color: 'var(--text-primary)' }}>
                <HighlightedText text={customer.name || '(name missing)'} query={matchedQuery} />
              </p>
              <p className="break-words font-data text-base" style={{ color: 'var(--text-muted)' }}>
                <HighlightedText text={customer.loanNumber} query={matchedQuery} />
                {' · '}
                {customer.phones.length > 0 ? (
                  customer.phones.map((entry, index) => (
                    <span key={entry.number}>
                      {index > 0 && ', '}
                      <HighlightedText text={entry.number} query={matchedQuery} />
                    </span>
                  ))
                ) : (
                  'no phone on file'
                )}
              </p>
              {customer.isBlacklisted && (
                <p className="mt-1 font-display text-[8px]" style={{ color: 'var(--accent-red)' }}>
                  🚫 BLACKLISTED
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

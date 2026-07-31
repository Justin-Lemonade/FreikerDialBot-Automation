import { useState } from 'react';
import { api, ApiError } from '../api/client';
import type { Customer } from '../types';

interface Props {
  onSelectCustomer: (customer: Customer) => void;
}

/**
 * Wraps the existing, already-tested GET /customer/search endpoint
 * (Database.search_customers -- matches loan number, name, full name,
 * and phone substring). No new backend surface here, just a Mini App
 * page for a capability that previously only existed via Telegram's
 * /customer command.
 */
export const Search = ({ onSelectCustomer }: Props) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Customer[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);

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
      setHasSearched(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Search failed. Please try again.');
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="retro-panel p-4">
        <p className="mb-3 font-display text-[9px]" style={{ color: 'var(--text-muted)' }}>
          FIND THE CLIENT'S
        </p>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') runSearch(query);
          }}
          placeholder="Name, loan number, or phone"
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
                {customer.name || '(name missing)'}
              </p>
              <p className="break-words font-data text-base" style={{ color: 'var(--text-muted)' }}>
                {customer.loanNumber} · {customer.phone || 'no phone on file'}
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

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
      <div className="rounded-[28px] border border-white/10 bg-slate-900/70 p-4">
        <p className="mb-3 text-sm font-semibold text-slate-300">Search Customers</p>
        <input
          value={query}
          onChange={(event) => {
            const value = event.target.value;
            setQuery(value);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') runSearch(query);
          }}
          placeholder="Name, loan number, or phone"
          className="min-h-[48px] w-full rounded-2xl border border-white/10 bg-slate-800 px-4 text-base outline-none placeholder:text-slate-500"
        />
        <button
          onClick={() => runSearch(query)}
          disabled={isSearching}
          className="mt-3 min-h-[48px] w-full rounded-2xl bg-emerald-500 px-4 text-sm font-semibold text-slate-950 active:scale-[0.98] disabled:opacity-60"
        >
          {isSearching ? 'Searching…' : '🔍 Search'}
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-4 text-center text-sm text-red-300">
          {error}
        </div>
      )}

      {hasSearched && !error && results.length === 0 && (
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 text-center text-sm text-slate-400">
          No customers found matching "{query}".
        </div>
      )}

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((customer) => (
            <button
              key={customer.id}
              onClick={() => onSelectCustomer(customer)}
              className="w-full rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-left active:scale-[0.98]"
            >
              <p className="font-semibold">{customer.name || '(name missing)'}</p>
              <p className="text-sm text-slate-400">
                {customer.loanNumber} · {customer.phone || 'no phone on file'}
              </p>
              {customer.isBlacklisted && (
                <p className="mt-1 text-xs font-semibold text-red-300">🚫 Blacklisted</p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

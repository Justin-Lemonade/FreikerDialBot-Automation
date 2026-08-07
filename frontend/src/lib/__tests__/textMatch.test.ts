import { describe, expect, it } from 'vitest';
import { splitOnMatch } from '../textMatch';

describe('splitOnMatch', () => {
  it('returns the whole text unmatched when there is no query', () => {
    expect(splitOnMatch('John Smith', '')).toEqual([{ text: 'John Smith', isMatch: false }]);
  });

  it('returns the whole text unmatched when there is no text', () => {
    expect(splitOnMatch('', 'john')).toEqual([{ text: '', isMatch: false }]);
  });

  it('splits a single match in the middle of the text', () => {
    expect(splitOnMatch('John Smith', 'Smi')).toEqual([
      { text: 'John ', isMatch: false },
      { text: 'Smi', isMatch: true },
      { text: 'th', isMatch: false },
    ]);
  });

  it('matches case-insensitively but preserves original casing in output', () => {
    expect(splitOnMatch('John Smith', 'smith')).toEqual([
      { text: 'John ', isMatch: false },
      { text: 'Smith', isMatch: true },
    ]);
  });

  it('matches a query at the very start of the text', () => {
    expect(splitOnMatch('Smith, John', 'Smith')).toEqual([
      { text: 'Smith', isMatch: true },
      { text: ', John', isMatch: false },
    ]);
  });

  it('matches every non-overlapping occurrence, not just the first', () => {
    // "ana banana": 'ana' matches at index 0, then again at index 5
    // (inside "banana"). The scan advances past each match rather than
    // overlapping, so the 'ana' that would start at index 7 (sharing
    // its leading 'a' with the match at 5) is correctly not
    // double-counted -- same behavior a plain, non-overlapping
    // substring scan should have.
    expect(splitOnMatch('ana banana', 'ana')).toEqual([
      { text: 'ana', isMatch: true },
      { text: ' b', isMatch: false },
      { text: 'ana', isMatch: true },
      { text: 'na', isMatch: false },
    ]);
  });

  it('returns the whole text unmatched when the query is not found', () => {
    expect(splitOnMatch('John Smith', 'xyz')).toEqual([{ text: 'John Smith', isMatch: false }]);
  });

  it('matches a phone-number-shaped query the same way Database.search_customers would', () => {
    expect(splitOnMatch('+15550001234', '5550001234')).toEqual([
      { text: '+1', isMatch: false },
      { text: '5550001234', isMatch: true },
    ]);
  });
});

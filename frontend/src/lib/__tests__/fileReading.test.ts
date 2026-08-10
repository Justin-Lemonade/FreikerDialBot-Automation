import { describe, expect, it } from 'vitest';
import { readFileAsBase64, readFileAsText } from '../fileReading';

describe('readFileAsText', () => {
  it('resolves with the file contents as a string', async () => {
    const file = new File(['{"loan_number": "X001"}'], 'customers.json', { type: 'application/json' });
    await expect(readFileAsText(file)).resolves.toBe('{"loan_number": "X001"}');
  });

  it('resolves with an empty string for an empty file', async () => {
    const file = new File([], 'empty.json', { type: 'application/json' });
    await expect(readFileAsText(file)).resolves.toBe('');
  });
});

describe('readFileAsBase64', () => {
  it('resolves with base64-encoded content, without the data-URL prefix', async () => {
    const file = new File(['hello'], 'greeting.txt', { type: 'text/plain' });
    const result = await readFileAsBase64(file);
    // "hello" -> base64 "aGVsbG8="
    expect(result).toBe('aGVsbG8=');
    expect(result.startsWith('data:')).toBe(false);
  });

  it('round-trips through atob back to the original content', async () => {
    const original = 'Ada,Lovelace,+15550001111';
    const file = new File([original], 'customers.csv', { type: 'text/csv' });
    const encoded = await readFileAsBase64(file);
    expect(atob(encoded)).toBe(original);
  });
});

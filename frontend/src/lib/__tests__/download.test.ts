import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadBlob } from '../download';

describe('downloadBlob', () => {
  let createObjectURLSpy: ReturnType<typeof vi.fn>;
  let revokeObjectURLSpy: ReturnType<typeof vi.fn>;
  let clickSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // jsdom doesn't implement these -- stub them so downloadBlob's real
    // logic (create URL, click a real <a>, clean up) runs against
    // something, rather than mocking downloadBlob itself away.
    createObjectURLSpy = vi.fn(() => 'blob:mock-url');
    revokeObjectURLSpy = vi.fn();
    URL.createObjectURL = createObjectURLSpy as unknown as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURLSpy as unknown as typeof URL.revokeObjectURL;
    clickSpy = vi.fn();
    HTMLAnchorElement.prototype.click = clickSpy as unknown as () => void;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates an object URL for the given blob', () => {
    const blob = new Blob(['a,b,c'], { type: 'text/csv' });
    downloadBlob(blob, 'customers.csv');
    expect(createObjectURLSpy).toHaveBeenCalledWith(blob);
  });

  it('sets the download filename and triggers a click', () => {
    const blob = new Blob(['{}'], { type: 'application/json' });
    downloadBlob(blob, 'customers.json');
    expect(clickSpy).toHaveBeenCalledTimes(1);
  });

  it('revokes the object URL after triggering the download (no leaked memory)', () => {
    const blob = new Blob(['data'], { type: 'text/csv' });
    downloadBlob(blob, 'export.csv');
    expect(revokeObjectURLSpy).toHaveBeenCalledWith('blob:mock-url');
  });

  it('removes the temporary link element from the DOM afterward', () => {
    const blob = new Blob(['data'], { type: 'text/csv' });
    const before = document.querySelectorAll('a').length;
    downloadBlob(blob, 'export.csv');
    const after = document.querySelectorAll('a').length;
    expect(after).toBe(before);
  });
});

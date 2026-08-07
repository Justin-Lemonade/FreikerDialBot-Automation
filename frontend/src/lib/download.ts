/** Triggers a browser download of `blob` as `filename` via a temporary
 * object URL. Shared by every place that downloads a real file from
 * the backend (Commands' "export" command and button, SessionComplete's
 * Export button) so the download mechanics only need to be right once. */
export const downloadBlob = (blob: Blob, filename: string): void => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

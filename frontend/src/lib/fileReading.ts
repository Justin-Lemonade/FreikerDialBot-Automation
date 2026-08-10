/** Reads a File's contents as plain text (for .json imports -- the
 * backend's /import endpoint takes raw JSON text for format="json",
 * same as an uploaded .json file on the Telegram bot side). */
export const readFileAsText = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error ?? new Error('Could not read file.'));
    reader.readAsText(file);
  });

/** Reads a File's contents as base64 (for .xlsx imports -- the backend
 * has no multipart upload handling, so binary files are sent as a
 * base64 string field like every other value this API accepts). Strips
 * the "data:...;base64," prefix readAsDataURL adds, since the backend
 * expects raw base64. */
export const readFileAsBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? '');
      const commaIndex = result.indexOf(',');
      resolve(commaIndex === -1 ? result : result.slice(commaIndex + 1));
    };
    reader.onerror = () => reject(reader.error ?? new Error('Could not read file.'));
    reader.readAsDataURL(file);
  });

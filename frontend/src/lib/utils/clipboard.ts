import { toast } from 'sonner';

/**
 * Copy text to clipboard with toast notifications.
 * @param text - The text to copy
 * @param successMessage - Optional custom success message (default: 'Copied to clipboard')
 * @returns Promise<boolean> - true if successful, false otherwise
 */
export async function copyToClipboard(
  text: string,
  successMessage = 'Copied to clipboard'
): Promise<boolean> {
  if (!navigator.clipboard) {
    toast.error('Clipboard not supported');
    return false;
  }

  try {
    await navigator.clipboard.writeText(text);
    toast.success(successMessage);
    return true;
  } catch {
    toast.error('Failed to copy to clipboard');
    return false;
  }
}

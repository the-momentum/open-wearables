/**
 * Helpers for planning S3 / MinIO multipart uploads on the client.
 *
 * Mirrors the backend limits (see backend/app/schemas/providers/apple/apple_xml/multipart.py):
 * parts are 5 MiB–5 GiB (the final part may be smaller) and there are at most
 * 10,000 parts per upload.
 */

export const MIN_PART_SIZE = 5 * 1024 * 1024; // 5 MiB
export const MAX_PARTS = 10_000;
export const DEFAULT_PART_SIZE = 100 * 1024 * 1024; // 100 MiB
/** How many parts to upload concurrently. */
export const PART_UPLOAD_CONCURRENCY = 4;

/** Trim transport whitespace without changing the object store's opaque ETag. */
export function normalizeMultipartEtag(etag: string): string {
  return etag.trim();
}

export interface PartPlan {
  /** 1-based part number, as required by S3. */
  partNumber: number;
  /** Byte offset of the part start (inclusive). */
  start: number;
  /** Byte offset of the part end (exclusive). */
  end: number;
}

/**
 * Split a file of `fileSize` bytes into ordered part ranges of at most
 * `partSize` bytes each. The final part carries the remainder.
 */
export function planMultipartParts(
  fileSize: number,
  partSize: number
): PartPlan[] {
  if (fileSize <= 0) return [];
  const effectivePartSize = Math.max(partSize, MIN_PART_SIZE);

  const parts: PartPlan[] = [];
  let start = 0;
  let partNumber = 1;
  while (start < fileSize) {
    const end = Math.min(start + effectivePartSize, fileSize);
    parts.push({ partNumber, start, end });
    start = end;
    partNumber += 1;
  }
  return parts;
}

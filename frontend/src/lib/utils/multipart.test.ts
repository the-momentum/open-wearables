import { describe, it, expect } from 'vitest';
import {
  planMultipartParts,
  MIN_PART_SIZE,
  DEFAULT_PART_SIZE,
  normalizeMultipartEtag,
} from './multipart';

describe('planMultipartParts', () => {
  it('returns no parts for an empty file', () => {
    expect(planMultipartParts(0, DEFAULT_PART_SIZE)).toEqual([]);
  });

  it('produces a single part for a file smaller than the part size', () => {
    const parts = planMultipartParts(10, DEFAULT_PART_SIZE);
    expect(parts).toEqual([{ partNumber: 1, start: 0, end: 10 }]);
  });

  it('splits a file into contiguous, ordered, gapless parts', () => {
    const partSize = MIN_PART_SIZE;
    const fileSize = partSize * 2 + 123; // two full parts + a remainder
    const parts = planMultipartParts(fileSize, partSize);

    expect(parts).toHaveLength(3);
    expect(parts.map((p) => p.partNumber)).toEqual([1, 2, 3]);
    // first byte covered, last byte covered, no gaps/overlaps
    expect(parts[0].start).toBe(0);
    expect(parts.at(-1)?.end).toBe(fileSize);
    for (let i = 1; i < parts.length; i++) {
      expect(parts[i].start).toBe(parts[i - 1].end);
    }
    // remainder lands in the final part
    expect(parts.at(-1)!.end - parts.at(-1)!.start).toBe(123);
  });

  it('every non-final part is exactly the part size', () => {
    const partSize = MIN_PART_SIZE;
    const parts = planMultipartParts(partSize * 3, partSize);
    for (const part of parts) {
      expect(part.end - part.start).toBe(partSize);
    }
  });

  it('never uses a part size below the S3 minimum', () => {
    // Ask for a 1-byte part size; planner must clamp to MIN_PART_SIZE.
    const parts = planMultipartParts(MIN_PART_SIZE + 1, 1);
    expect(parts).toHaveLength(2);
    expect(parts[0].end - parts[0].start).toBe(MIN_PART_SIZE);
  });
});

describe('normalizeMultipartEtag', () => {
  it('preserves the quotes returned by AWS S3 and MinIO', () => {
    expect(normalizeMultipartEtag('  "abc123"  ')).toBe('"abc123"');
  });

  it('preserves an unquoted ETag', () => {
    expect(normalizeMultipartEtag('abc123-4')).toBe('abc123-4');
  });
});

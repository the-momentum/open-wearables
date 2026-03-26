import { describe, expect, it } from 'vitest';
import { formatBedtime } from './format';

describe('formatBedtime', () => {
  it('formats integer minutes without regression', () => {
    expect(formatBedtime(690)).toBe('11:30 AM');
  });

  it('rounds fractional minutes near hour boundary without displaying :60', () => {
    expect(formatBedtime(719.7)).toBe('12:00 PM');
    expect(formatBedtime(59.8)).toBe('1:00 AM');
  });

  it('wraps hours when rounding pushes past end of day', () => {
    expect(formatBedtime(1439.7)).toBe('12:00 AM');
  });
});

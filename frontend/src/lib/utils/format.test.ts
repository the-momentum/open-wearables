import { format } from 'date-fns';
import { describe, expect, it } from 'vitest';
import { formatBedtime, parseApiDate } from './format';

describe('parseApiDate', () => {
  it('keeps the calendar day for a date-only string regardless of timezone', () => {
    // `new Date("2026-06-09")` parses as UTC midnight, which renders as Jun 8
    // in any negative-UTC timezone. parseApiDate must stay on Jun 9.
    const d = parseApiDate('2026-06-09');
    expect(d.getFullYear()).toBe(2026);
    expect(d.getMonth()).toBe(5); // June (0-indexed)
    expect(d.getDate()).toBe(9);
  });

  it('round-trips through date-fns format without shifting', () => {
    expect(format(parseApiDate('2026-06-09'), 'yyyy-MM-dd')).toBe('2026-06-09');
    expect(format(parseApiDate('2026-01-01'), 'EEE, MMM d')).toBe('Thu, Jan 1');
  });
});

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

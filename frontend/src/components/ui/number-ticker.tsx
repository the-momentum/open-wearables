import { ComponentPropsWithoutRef, useEffect, useMemo, useRef } from 'react';
import { useInView, useMotionValue, useSpring } from 'motion/react';

import { cn } from '@/lib/utils';

interface NumberTickerProps extends ComponentPropsWithoutRef<'span'> {
  value: number;
  startValue?: number;
  direction?: 'up' | 'down';
  delay?: number;
  decimalPlaces?: number;
  /** Custom formatter for the displayed value (e.g. compact K/M/B). Overrides decimalPlaces. */
  format?: (value: number) => string;
}

export function NumberTicker({
  value,
  startValue = 0,
  direction = 'up',
  delay = 0,
  className,
  decimalPlaces = 0,
  format,
  ...props
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(direction === 'down' ? value : startValue);
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 100,
  });
  const isInView = useInView(ref, { once: true, margin: '0px' });

  // Reuse one formatter instead of allocating a new Intl.NumberFormat on every animation frame.
  const formatter = useMemo(
    () =>
      new Intl.NumberFormat('en-US', {
        minimumFractionDigits: decimalPlaces,
        maximumFractionDigits: decimalPlaces,
      }),
    [decimalPlaces]
  );

  useEffect(() => {
    if (isInView) {
      const timer = setTimeout(() => {
        motionValue.set(direction === 'down' ? startValue : value);
      }, delay * 1000);
      return () => clearTimeout(timer);
    }
  }, [motionValue, isInView, delay, value, direction, startValue]);

  useEffect(
    () =>
      springValue.on('change', (latest) => {
        if (ref.current) {
          // Quantize the mid-animation spring value to whole units (decimalPlaces defaults to 0)
          // before formatting, so counts don't flash fractional values like "4.8" while animating.
          const current = Number(latest.toFixed(decimalPlaces));
          ref.current.textContent = format
            ? format(current)
            : formatter.format(current);
        }
      }),
    [springValue, formatter, decimalPlaces, format]
  );

  return (
    <span
      ref={ref}
      className={cn(
        'inline-block tracking-wider text-black tabular-nums dark:text-foreground',
        className
      )}
      {...props}
    >
      {format ? format(startValue) : startValue}
    </span>
  );
}

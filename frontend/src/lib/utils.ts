import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export function truncateId(id: string, maxLength = 12) {
  if (id.length <= maxLength) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

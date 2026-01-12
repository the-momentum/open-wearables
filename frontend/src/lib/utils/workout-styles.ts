export interface WorkoutStyle {
  color: string;
  icon: string;
  label: string;
}

export function getWorkoutStyle(type: string | null | undefined): WorkoutStyle {
  const t = (type || '').toLowerCase();

  if (t.includes('swim')) {
    return {
      color: 'bg-blue-500/10 border-blue-500/20 text-blue-500',
      icon: '🏊‍♂️',
      label: 'Swimming',
    };
  }

  if (t.includes('cycle') || t.includes('bike')) {
    return {
      color: 'bg-orange-500/10 border-orange-500/20 text-orange-500',
      icon: '🚴',
      label: 'Cycling',
    };
  }

  if (t.includes('strength') || t.includes('weight')) {
    return {
      color: 'bg-amber-900/20 border-amber-700/30 text-amber-600',
      icon: '💪',
      label: 'Gym',
    };
  }

  if (t.includes('walk')) {
    return {
      color: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500',
      icon: '🚶',
      label: 'Walking',
    };
  }

  if (t.includes('run')) {
    return {
      color: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-500',
      icon: '🏃',
      label: 'Running',
    };
  }

  if (t.includes('treadmill')) {
    return {
      color: 'bg-indigo-500/10 border-indigo-500/20 text-indigo-500',
      icon: '🏃',
      label: 'Treadmill',
    };
  }

  if (t.includes('yoga')) {
    return {
      color: 'bg-rose-500/10 border-rose-500/20 text-rose-500',
      icon: '🧘',
      label: 'Yoga',
    };
  }

  if (t.includes('hiit')) {
    return {
      color: 'bg-red-500/10 border-red-500/20 text-red-500',
      icon: '🔥',
      label: 'HIIT',
    };
  }

  // Fallback
  const rawLabel = type || 'Workout';
  // Capitalize first letter of each word for the fallback label
  const formattedLabel = rawLabel
    .split(/[_\s]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');

  return {
    color: 'bg-zinc-800 border-zinc-700 text-zinc-400',
    icon: '🏅',
    label: formattedLabel,
  };
}

interface MetricCardProps {
  icon: React.ElementType;
  iconColor: string;
  iconBgColor: string;
  value: string;
  label: string;
  isClickable?: boolean;
  isSelected?: boolean;
  glowColor?: string;
  onClick?: () => void;
}

/**
 * A reusable metric card component for displaying stats.
 * Can be static or clickable with selection state.
 */
export function MetricCard({
  icon: Icon,
  iconColor,
  iconBgColor,
  value,
  label,
  isClickable = false,
  isSelected = false,
  glowColor = '',
  onClick,
}: MetricCardProps) {
  const baseClasses =
    'p-4 border rounded-lg bg-zinc-900/30 transition-all duration-200';

  if (isClickable) {
    return (
      <button
        onClick={onClick}
        className={`${baseClasses} text-left cursor-pointer
          ${
            isSelected
              ? `border-zinc-600 ${glowColor}`
              : 'border-zinc-800 hover:border-zinc-700 hover:shadow-[0_0_10px_rgba(255,255,255,0.1)]'
          }
        `}
      >
        <div className="flex items-center gap-3 mb-3">
          <div className={`p-2 ${iconBgColor} rounded-lg`}>
            <Icon className={`h-5 w-5 ${iconColor}`} />
          </div>
        </div>
        <p className="text-2xl font-semibold text-white">{value}</p>
        <p className="text-xs text-zinc-500 mt-1">{label}</p>
      </button>
    );
  }

  return (
    <div className={`${baseClasses} border-zinc-800`}>
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 ${iconBgColor} rounded-lg`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
      <p className="text-2xl font-semibold text-white">{value}</p>
      <p className="text-xs text-zinc-500 mt-1">{label}</p>
    </div>
  );
}

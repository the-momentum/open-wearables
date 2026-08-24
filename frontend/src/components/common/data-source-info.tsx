import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { SourceBadge, providerLabel } from '@/components/common/source-badge';
import {
  deviceTypeInfo,
  DeviceTypeIcon,
} from '@/components/common/device-type';
import { cn } from '@/lib/utils';
import type { SourceMetadata } from '@/lib/api/types';

const NO_DEVICE_INFO = 'Device info not available';

export function DataSourceInfo({
  source,
  className = '',
}: {
  source: SourceMetadata | null | undefined;
  className?: string;
}) {
  if (!source) return null;

  const { label: deviceTypeLabel } = deviceTypeInfo(source.device_type);
  const deviceName = source.device_name?.trim() || null;
  // Native API integrations store the provider key as the source ("garmin"/"garmin"),
  // so it only carries information for HealthKit / Health Connect writers.
  const showSource =
    source.source && source.source !== source.provider ? source.source : null;

  return (
    <div className={cn('flex min-w-0 items-center gap-1.5', className)}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="shrink-0">
            <SourceBadge provider={source.provider} />
          </span>
        </TooltipTrigger>
        <TooltipContent>
          Provider: {providerLabel(source.provider)}
        </TooltipContent>
      </Tooltip>

      {showSource && (
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="min-w-0 truncate text-[10px] text-muted-foreground">
              {showSource}
            </span>
          </TooltipTrigger>
          <TooltipContent>
            Written by <strong>{showSource}</strong> into{' '}
            {providerLabel(source.provider)}
          </TooltipContent>
        </Tooltip>
      )}

      <Tooltip>
        <TooltipTrigger asChild>
          <span className="flex min-w-0 items-center gap-1 text-[10px] text-muted-foreground">
            <DeviceTypeIcon
              deviceType={source.device_type}
              className="h-3 w-3 shrink-0"
            />
            <span className="truncate">{deviceName ?? NO_DEVICE_INFO}</span>
          </span>
        </TooltipTrigger>
        <TooltipContent>
          {deviceName ? (
            <div className="space-y-0.5">
              <div>
                {deviceTypeLabel}: {deviceName}
              </div>
              {source.device && source.device !== deviceName && (
                <div className="text-muted-foreground">
                  Model: {source.device}
                </div>
              )}
            </div>
          ) : (
            NO_DEVICE_INFO
          )}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

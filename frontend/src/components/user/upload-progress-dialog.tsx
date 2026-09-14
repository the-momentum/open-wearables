import { CheckCircle2, AlertCircle, Loader2, FileText } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { UploadProgressState } from '@/hooks/api/use-users';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

interface UploadProgressDialogProps {
  progress: UploadProgressState;
  /** Called when the dialog is dismissed (only possible once not uploading). */
  onClose: () => void;
}

export function UploadProgressDialog({
  progress,
  onClose,
}: UploadProgressDialogProps) {
  const { phase, percent, fileName, fileSize, errorMessage } = progress;
  const open = phase !== 'idle';
  const isUploading = phase === 'uploading';

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        // Block dismissal while the upload is in flight.
        if (!next && !isUploading) onClose();
      }}
    >
      <DialogContent
        // Radix focuses the panel on open; with no focusable control inside during
        // upload, the browser's focus outline would show — suppress it here.
        // Also hide the close (X) button while uploading so the transfer isn't interrupted.
        className={cn(
          'outline-none focus:outline-none focus-visible:outline-none',
          isUploading && '[&>button:last-of-type]:hidden'
        )}
        onEscapeKeyDown={(e) => isUploading && e.preventDefault()}
        onInteractOutside={(e) => isUploading && e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>
            {phase === 'success'
              ? 'Upload complete'
              : phase === 'error'
                ? 'Upload failed'
                : 'Uploading Apple Health XML'}
          </DialogTitle>
          <DialogDescription>
            {phase === 'success'
              ? 'The file was uploaded. Processing will continue in the background.'
              : phase === 'error'
                ? 'The file could not be uploaded.'
                : 'Keep this tab open until the upload finishes.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-start gap-3 rounded-lg border border-border/60 bg-muted/40 p-3">
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-foreground">
              {fileName ?? 'File'}
            </p>
            {fileSize !== null && (
              <p className="text-xs text-muted-foreground">
                {formatBytes(fileSize)}
              </p>
            )}
          </div>
          <StatusIcon phase={phase} />
        </div>

        {phase === 'error' ? (
          <p className="text-sm text-destructive">
            {errorMessage ?? 'Something went wrong during the upload.'}
          </p>
        ) : (
          <div className="space-y-2">
            <Progress
              value={percent}
              className="h-2 bg-white/10"
              indicatorClassName={cn(
                'transition-all',
                phase === 'success' ? 'bg-emerald-400/90' : 'bg-foreground'
              )}
            />
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                {phase === 'success'
                  ? 'Done'
                  : fileSize !== null
                    ? `${formatBytes((fileSize * percent) / 100)} of ${formatBytes(fileSize)}`
                    : 'Uploading…'}
              </span>
              <span className="tabular-nums">{percent}%</span>
            </div>
          </div>
        )}

        {!isUploading && (
          <DialogFooter>
            <Button
              variant={phase === 'error' ? 'secondary' : 'default'}
              onClick={onClose}
            >
              {phase === 'error' ? 'Close' : 'Done'}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

function StatusIcon({ phase }: { phase: UploadProgressState['phase'] }) {
  if (phase === 'success') {
    return <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-400/90" />;
  }
  if (phase === 'error') {
    return <AlertCircle className="h-5 w-5 shrink-0 text-destructive" />;
  }
  return (
    <Loader2 className="h-5 w-5 shrink-0 animate-spin text-muted-foreground" />
  );
}

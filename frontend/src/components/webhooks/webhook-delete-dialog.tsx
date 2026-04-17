import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { useDeleteWebhookEndpoint } from '@/hooks/api/use-webhooks';

interface WebhookDeleteDialogProps {
  endpointId: string | null;
  url?: string;
  onClose: () => void;
  onDeleted?: () => void;
}

export function WebhookDeleteDialog({
  endpointId,
  url,
  onClose,
  onDeleted,
}: WebhookDeleteDialogProps) {
  const remove = useDeleteWebhookEndpoint();

  return (
    <Dialog open={!!endpointId} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete webhook?</DialogTitle>
          <DialogDescription>
            Future events will no longer be delivered to this endpoint. This
            cannot be undone.
          </DialogDescription>
        </DialogHeader>
        {url && (
          <div className="p-3 bg-zinc-800 rounded-md">
            <p className="text-xs text-zinc-500">URL:</p>
            <code className="font-mono text-xs text-zinc-300 break-all">
              {url}
            </code>
          </div>
        )}
        <DialogFooter className="gap-3">
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() => {
              if (!endpointId) return;
              remove.mutate(endpointId, {
                onSuccess: () => {
                  onClose();
                  onDeleted?.();
                },
              });
            }}
          >
            {remove.isPending ? 'Deleting...' : 'Delete webhook'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

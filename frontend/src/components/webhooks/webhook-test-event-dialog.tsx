import { useState, useEffect } from 'react';
import { Loader2, Send } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  useSendTestWebhook,
  useWebhookEventTypes,
} from '@/hooks/api/use-webhooks';

interface WebhookTestEventDialogProps {
  endpointId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialEventType?: string;
}

const FALLBACK_EVENT = 'workout.created';

export function WebhookTestEventDialog({
  endpointId,
  open,
  onOpenChange,
  initialEventType,
}: WebhookTestEventDialogProps) {
  const eventTypes = useWebhookEventTypes();
  const send = useSendTestWebhook();
  const [eventType, setEventType] = useState(
    initialEventType ?? FALLBACK_EVENT
  );

  useEffect(() => {
    if (open && initialEventType) setEventType(initialEventType);
  }, [open, initialEventType]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Send test event</DialogTitle>
          <DialogDescription>
            Dispatches a sample payload to this endpoint so you can verify the
            integration end-to-end.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <Label htmlFor="test-event-type" className="text-zinc-300">
            Event type
          </Label>
          <select
            id="test-event-type"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-zinc-200"
          >
            {eventTypes.data?.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          <p className="text-[10px] text-zinc-600">
            {eventTypes.data?.find((t) => t.name === eventType)?.description}
          </p>
        </div>

        <DialogFooter className="gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={send.isPending || !eventType}
            onClick={() =>
              send.mutate(
                { id: endpointId, eventType },
                {
                  onSuccess: () => onOpenChange(false),
                }
              )
            }
          >
            {send.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                Send test
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

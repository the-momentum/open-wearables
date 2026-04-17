import { useNavigate } from '@tanstack/react-router';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useCreateWebhookEndpoint } from '@/hooks/api/use-webhooks';
import { WebhookForm } from './webhook-form';

interface WebhookCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function WebhookCreateDialog({
  open,
  onOpenChange,
}: WebhookCreateDialogProps) {
  const create = useCreateWebhookEndpoint();
  const navigate = useNavigate();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Create webhook endpoint</DialogTitle>
          <DialogDescription>
            We'll deliver subscribed events to this URL with a signed payload.
          </DialogDescription>
        </DialogHeader>
        <WebhookForm
          submitLabel="Create webhook"
          isSubmitting={create.isPending}
          onCancel={() => onOpenChange(false)}
          onSubmit={(data) => {
            create.mutate(
              {
                url: data.url,
                description: data.description ?? null,
                filter_types: data.filter_types ?? null,
                user_id: data.user_id ?? null,
              },
              {
                onSuccess: (created) => {
                  onOpenChange(false);
                  navigate({
                    to: '/webhooks/$endpointId',
                    params: { endpointId: created.id },
                  });
                },
              }
            );
          }}
        />
      </DialogContent>
    </Dialog>
  );
}

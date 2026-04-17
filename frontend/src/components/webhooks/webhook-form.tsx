import { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useWebhookEventTypes } from '@/hooks/api/use-webhooks';
import {
  webhookEndpointFormSchema,
  type WebhookEndpointFormData,
} from '@/lib/validation/webhooks.schemas';
import type { WebhookEndpoint } from '@/lib/api/types';

interface WebhookFormProps {
  initial?: WebhookEndpoint;
  isSubmitting?: boolean;
  submitLabel: string;
  onSubmit: (data: WebhookEndpointFormData) => void;
  onCancel?: () => void;
}

export function WebhookForm({
  initial,
  isSubmitting,
  submitLabel,
  onSubmit,
  onCancel,
}: WebhookFormProps) {
  const eventTypes = useWebhookEventTypes();
  const [eventFilter, setEventFilter] = useState('');

  const form = useForm<WebhookEndpointFormData>({
    resolver: zodResolver(webhookEndpointFormSchema),
    defaultValues: {
      url: initial?.url ?? '',
      description: initial?.description ?? '',
      filter_types: initial?.filter_types ?? [],
      user_id: initial?.user_id ?? '',
    },
  });

  useEffect(() => {
    if (initial) {
      form.reset({
        url: initial.url,
        description: initial.description ?? '',
        filter_types: initial.filter_types ?? [],
        user_id: initial.user_id ?? '',
      });
    }
  }, [initial, form]);

  const handleFormSubmit = form.handleSubmit((data) => {
    onSubmit({
      url: data.url.trim(),
      description: data.description?.trim() || undefined,
      filter_types: data.filter_types?.length ? data.filter_types : undefined,
      user_id: data.user_id?.trim() || undefined,
    });
  });

  const filtered = eventTypes.data?.filter((t) =>
    t.name.toLowerCase().includes(eventFilter.toLowerCase())
  );

  return (
    <form onSubmit={handleFormSubmit} className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="webhook-url" className="text-zinc-300">
          Endpoint URL
        </Label>
        <Input
          id="webhook-url"
          type="url"
          placeholder="https://example.com/webhooks/openwearables"
          {...form.register('url')}
          className="bg-zinc-800 border-zinc-700"
        />
        {form.formState.errors.url && (
          <p className="text-xs text-red-500">
            {form.formState.errors.url.message}
          </p>
        )}
        <p className="text-[10px] text-zinc-600">Must use HTTPS.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="webhook-description" className="text-zinc-300">
          Description{' '}
          <span className="text-zinc-600 font-normal">(optional)</span>
        </Label>
        <Input
          id="webhook-description"
          type="text"
          placeholder="Production ingestion pipeline"
          maxLength={500}
          {...form.register('description')}
          className="bg-zinc-800 border-zinc-700"
        />
        {form.formState.errors.description && (
          <p className="text-xs text-red-500">
            {form.formState.errors.description.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="webhook-user-id" className="text-zinc-300">
          User filter{' '}
          <span className="text-zinc-600 font-normal">(optional)</span>
        </Label>
        <Input
          id="webhook-user-id"
          type="text"
          placeholder="UUID - leave empty to receive events for all users"
          {...form.register('user_id')}
          className="bg-zinc-800 border-zinc-700 font-mono text-xs"
        />
        {form.formState.errors.user_id && (
          <p className="text-xs text-red-500">
            {form.formState.errors.user_id.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label className="text-zinc-300">
          Event types{' '}
          <span className="text-zinc-600 font-normal">
            (leave none selected to receive all)
          </span>
        </Label>
        {eventTypes.isLoading ? (
          <div className="flex items-center gap-2 text-xs text-zinc-500 py-2">
            <Loader2 className="h-3 w-3 animate-spin" />
            Loading event types...
          </div>
        ) : eventTypes.error ? (
          <p className="text-xs text-red-500">Failed to load event types.</p>
        ) : (
          <Controller
            control={form.control}
            name="filter_types"
            render={({ field }) => {
              const selected = new Set(field.value ?? []);
              const toggle = (name: string) => {
                const next = new Set(selected);
                if (next.has(name)) next.delete(name);
                else next.add(name);
                field.onChange(Array.from(next));
              };
              return (
                <div className="space-y-2">
                  <Input
                    type="text"
                    placeholder="Filter event types..."
                    value={eventFilter}
                    onChange={(e) => setEventFilter(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 h-8 text-xs"
                  />
                  <div className="flex flex-wrap gap-1.5 max-h-40 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-900/50 p-2">
                    {filtered?.length ? (
                      filtered.map((t) => {
                        const isOn = selected.has(t.name);
                        return (
                          <button
                            type="button"
                            key={t.name}
                            onClick={() => toggle(t.name)}
                            title={t.description}
                            className="focus:outline-none"
                          >
                            <Badge
                              variant={isOn ? 'default' : 'outline'}
                              className={
                                isOn
                                  ? 'cursor-pointer bg-white text-black hover:bg-zinc-200'
                                  : 'cursor-pointer border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-200'
                              }
                            >
                              {t.name}
                            </Badge>
                          </button>
                        );
                      })
                    ) : (
                      <p className="text-xs text-zinc-600 px-1 py-2">
                        No matching event types.
                      </p>
                    )}
                  </div>
                  {selected.size > 0 && (
                    <p className="text-[10px] text-zinc-600">
                      {selected.size} selected
                    </p>
                  )}
                </div>
              );
            }}
          />
        )}
      </div>

      <div className="flex justify-end gap-3 pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            submitLabel
          )}
        </Button>
      </div>
    </form>
  );
}

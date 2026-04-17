import { useEffect, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ChevronDown, ChevronRight, Loader2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useWebhookEventTypes } from '@/hooks/api/use-webhooks';
import {
  webhookEndpointFormSchema,
  type WebhookEndpointFormData,
} from '@/lib/validation/webhooks.schemas';
import type { WebhookEndpoint, WebhookEventType } from '@/lib/api/types';

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
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

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

  const allTypes = eventTypes.data ?? [];

  const childrenByGroup = new Map<string, WebhookEventType[]>(
    allTypes
      .filter((t) => t.child_events && t.child_events.length > 0)
      .map((t) => [
        t.name,
        (t.child_events ?? [])
          .map((cn) => allTypes.find((x) => x.name === cn))
          .filter(Boolean) as WebhookEventType[],
      ])
  );

  const granularSet = new Set(
    [...childrenByGroup.values()].flatMap((cs) => cs.map((c) => c.name))
  );

  // child name → parent group name (for mutual-exclusion logic)
  const childToGroup = new Map<string, string>(
    [...childrenByGroup.entries()].flatMap(([groupName, children]) =>
      children.map((c) => [c.name, groupName])
    )
  );

  const topLevel = allTypes.filter(
    (t) => !granularSet.has(t.name) || childrenByGroup.has(t.name)
  );

  const q = eventFilter.toLowerCase();
  const filteredTop = q
    ? allTypes.filter(
        (t) =>
          t.name.toLowerCase().includes(q) ||
          t.description.toLowerCase().includes(q)
      )
    : topLevel;

  const toggleExpanded = (name: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

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
                if (next.has(name)) {
                  next.delete(name);
                } else {
                  next.add(name);
                  // selecting a child → deselect its parent catch-all
                  const parentGroup = childToGroup.get(name);
                  if (parentGroup) next.delete(parentGroup);
                  // selecting a parent catch-all → deselect all its children
                  const ownChildren = childrenByGroup.get(name);
                  if (ownChildren)
                    ownChildren.forEach((c) => next.delete(c.name));
                }
                field.onChange(Array.from(next));
              };

              const toggleAllChildren = (
                groupName: string,
                children: WebhookEventType[]
              ) => {
                const allOn = children.every((c) => selected.has(c.name));
                const next = new Set(selected);
                if (allOn) {
                  children.forEach((c) => next.delete(c.name));
                } else {
                  children.forEach((c) => next.add(c.name));
                  // selecting specific events → deselect the catch-all parent
                  next.delete(groupName);
                  setExpandedGroups((prev) => new Set([...prev, groupName]));
                }
                field.onChange(Array.from(next));
              };

              const EventBadge = ({
                name,
                description,
                isOn,
                onToggle,
              }: {
                name: string;
                description: string;
                isOn: boolean;
                onToggle: () => void;
              }) => (
                <button
                  type="button"
                  onClick={onToggle}
                  title={description}
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
                    {name}
                  </Badge>
                </button>
              );

              return (
                <div className="space-y-2">
                  <Input
                    type="text"
                    placeholder="Filter event types..."
                    value={eventFilter}
                    onChange={(e) => setEventFilter(e.target.value)}
                    className="bg-zinc-800 border-zinc-700 h-8 text-xs"
                  />
                  <div className="flex flex-col gap-0.5 max-h-64 overflow-y-auto rounded-md border border-zinc-800 bg-zinc-900/50 p-2">
                    {filteredTop.length ? (
                      filteredTop.map((t) => {
                        const children = childrenByGroup.get(t.name);
                        const hasChildren = children && children.length > 0;
                        const isExpanded = expandedGroups.has(t.name);

                        if (!hasChildren) {
                          return (
                            <div
                              key={t.name}
                              className="flex items-center gap-1.5 py-0.5"
                            >
                              <EventBadge
                                name={t.name}
                                description={t.description}
                                isOn={selected.has(t.name)}
                                onToggle={() => toggle(t.name)}
                              />
                            </div>
                          );
                        }

                        const selectedCount = children.filter((c) =>
                          selected.has(c.name)
                        ).length;
                        const allChildrenOn = selectedCount === children.length;
                        const someChildrenOn =
                          selectedCount > 0 && !allChildrenOn;

                        return (
                          <div key={t.name}>
                            <div className="flex items-center gap-1.5 py-0.5">
                              {/* Expand/collapse chevron */}
                              <button
                                type="button"
                                onClick={() => toggleExpanded(t.name)}
                                className="text-zinc-500 hover:text-zinc-300 focus:outline-none flex-shrink-0"
                                title={
                                  isExpanded
                                    ? 'Collapse'
                                    : 'Expand specific events'
                                }
                              >
                                {isExpanded ? (
                                  <ChevronDown className="h-3 w-3" />
                                ) : (
                                  <ChevronRight className="h-3 w-3" />
                                )}
                              </button>

                              {/* Group catch-all badge */}
                              <EventBadge
                                name={t.name}
                                description={`${t.description}\n\nCatch-all: fires for every specific metric in this group. Select individual metrics below for finer control.`}
                                isOn={selected.has(t.name)}
                                onToggle={() => toggle(t.name)}
                              />

                              {/* Select all / deselect all children */}
                              <button
                                type="button"
                                onClick={() =>
                                  toggleAllChildren(t.name, children)
                                }
                                className="text-[10px] text-zinc-500 hover:text-zinc-300 focus:outline-none flex-shrink-0"
                                title={
                                  allChildrenOn
                                    ? 'Deselect all specific events'
                                    : 'Select all specific events'
                                }
                              >
                                {allChildrenOn ? (
                                  <span className="text-zinc-300">
                                    − all specific
                                  </span>
                                ) : someChildrenOn ? (
                                  <span>
                                    {selectedCount}/{children.length} specific
                                  </span>
                                ) : (
                                  '+ all specific'
                                )}
                              </button>
                            </div>

                            {isExpanded && (
                              <div className="mt-1 ml-4 flex flex-wrap gap-1.5 border-l border-zinc-800 pl-2.5 pb-1.5">
                                {children.map((c) => (
                                  <EventBadge
                                    key={c.name}
                                    name={c.name}
                                    description={c.description}
                                    isOn={selected.has(c.name)}
                                    onToggle={() => toggle(c.name)}
                                  />
                                ))}
                              </div>
                            )}
                          </div>
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
                      {selected.size} event type{selected.size !== 1 ? 's' : ''}{' '}
                      selected
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

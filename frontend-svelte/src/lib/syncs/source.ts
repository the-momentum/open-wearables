import ArrowDownToLine from '@lucide/svelte/icons/arrow-down-to-line';
import CircleHelp from '@lucide/svelte/icons/circle-help';
import FileUp from '@lucide/svelte/icons/file-up';
import History from '@lucide/svelte/icons/history';
import Link2 from '@lucide/svelte/icons/link-2';
import Smartphone from '@lucide/svelte/icons/smartphone';
import Webhook from '@lucide/svelte/icons/webhook';
import type { Component } from 'svelte';
import { humanise } from '$lib/utils/text';

/**
 * Named here rather than derived from the slug: capitalising `sdk` gives "Sdk"
 * and `xml_import` gives "Xml import".
 */
const SOURCES: Record<string, { icon: Component; label: string }> = {
	pull: { icon: ArrowDownToLine, label: 'Pull' },
	webhook: { icon: Webhook, label: 'Webhook' },
	sdk: { icon: Smartphone, label: 'SDK' },
	backfill: { icon: History, label: 'Backfill' },
	xml_import: { icon: FileUp, label: 'XML import' },
	linked_account: { icon: Link2, label: 'Linked account' }
};

/** Both fall back rather than render nothing: the backend may add a source. */
export const sourceIcon = (source: string): Component => SOURCES[source]?.icon ?? CircleHelp;

export const sourceLabel = (source: string): string => SOURCES[source]?.label ?? humanise(source);

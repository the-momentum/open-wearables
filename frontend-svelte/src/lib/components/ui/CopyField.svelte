<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Copy from '@lucide/svelte/icons/copy';
	import { createCopier } from '$lib/utils/clipboard.svelte';
	import { cn } from '$lib/utils/cn';

	let { label, value, mono = false }: { label: string; value: string; mono?: boolean } = $props();

	const copier = createCopier();
	const fieldId = $props.id();
</script>

<div class="flex flex-col gap-1.5">
	<label for={fieldId} class="text-sm font-medium">{label}</label>
	<div class="flex items-center gap-2">
		<input
			id={fieldId}
			readonly
			{value}
			class={cn(
				'min-h-11 min-w-0 flex-1 rounded-lg border border-border bg-surface-muted px-3 text-sm',
				mono && 'text-center font-mono tracking-widest'
			)}
		/>
		<button
			type="button"
			onclick={() => copier.copy(value)}
			aria-label={copier.copied ? `${label} copied` : `Copy ${label}`}
			class="grid size-11 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
		>
			{#if copier.copied}
				<Check size={16} aria-hidden="true" class="text-success" />
			{:else}
				<Copy size={16} aria-hidden="true" />
			{/if}
		</button>
	</div>
</div>

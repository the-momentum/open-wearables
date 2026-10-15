<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import CopyButton from './CopyButton.svelte';

	let { label, value, mono = false }: { label: string; value: string; mono?: boolean } = $props();

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
		<CopyButton {value} {label} place="field" />
	</div>
</div>

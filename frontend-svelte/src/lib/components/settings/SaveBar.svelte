<script lang="ts">
	import { enhance } from '$app/forms';
	import Button from '$lib/components/ui/Button.svelte';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let {
		action,
		note,
		payload
	}: {
		action: string;
		/** What is about to be saved, in the reader's words. */
		note: string;
		/** The draft, as the one hidden field the action reads. */
		payload: Record<string, string>;
	} = $props();

	const submit = createSubmitFlag();
</script>

<!-- Pinned, because the change that needs saving can be scrolled off the top of
     a long list. Clear of the mobile bottom bar and the home indicator. -->
<form
	method="POST"
	{action}
	use:enhance={submit.enhance}
	class="fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-30 mx-auto flex
		w-[min(28rem,calc(100vw-2rem))] items-center justify-between gap-3 rounded-xl border
		border-border bg-surface px-4 py-3 shadow-lg lg:bottom-6"
>
	{#each Object.entries(payload) as [name, value] (name)}
		<input type="hidden" {name} {value} />
	{/each}

	<p class="text-xs text-foreground/90">{note}</p>
	<Button type="submit" size="sm" disabled={submit.submitting}>
		{submit.submitting ? 'Saving…' : 'Save changes'}
	</Button>
</form>

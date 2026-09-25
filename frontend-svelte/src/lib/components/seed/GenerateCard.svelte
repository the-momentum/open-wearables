<script lang="ts">
	import Play from '@lucide/svelte/icons/play';
	import Users from '@lucide/svelte/icons/users';
	import { enhance } from '$app/forms';
	import { resolve } from '$app/paths';
	import Alert from '$lib/components/ui/Alert.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import CopyButton from '$lib/components/ui/CopyButton.svelte';
	import { INLINE_LINK, MICRO, MONO } from '$lib/components/ui/typography';
	import { createSubmitFlag } from '$lib/utils/forms.svelte';

	let {
		payload,
		summary,
		problems,
		message,
		queued
	}: {
		/** The draft and its preset, as the one field the action reads. */
		payload: string;
		summary: { who: string; what: string; when: string };
		problems: string[];
		message?: string;
		queued?: { seed: number | null; users: number };
	} = $props();

	const submit = createSubmitFlag();
</script>

<Card icon={Play} title="Generate">
	<form method="POST" action="?/generate" use:enhance={submit.enhance} class="flex flex-col gap-4">
		<input type="hidden" name="seed" value={payload} />

		<!-- The whole request read back in one sentence, so nothing a collapsed
		     section holds comes as a surprise. -->
		<p class="text-sm text-foreground/90">
			<strong class="font-medium text-foreground">{summary.who}</strong>, each with {summary.what},
			over the {summary.when}.
		</p>

		{#if message}
			<Alert>{message}</Alert>
		{:else if problems.length > 0}
			<Alert tone="warning">{problems[0]}</Alert>
		{/if}

		{#if queued}
			<div
				class="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-success/30 bg-success/5 px-3 py-2.5 text-sm"
			>
				<span class="text-foreground/90">
					Queued {queued.users === 1 ? 'one user' : `${queued.users} users`}.
				</span>
				{#if queued.seed !== null}
					<!-- The seed is in the generated names too; this is the one to reuse. -->
					<span class="inline-flex items-center gap-1 {MICRO}">
						seed <code class="text-foreground {MONO}">{queued.seed}</code>
						<CopyButton value={String(queued.seed)} label="seed" />
					</span>
				{/if}
				<a
					href={resolve('/users')}
					class="inline-flex items-center gap-1.5 sm:ml-auto {INLINE_LINK}"
				>
					<Users size={14} aria-hidden="true" />
					They appear in Users as the job runs
				</a>
			</div>
		{/if}

		<div>
			<Button type="submit" disabled={problems.length > 0 || submit.submitting}>
				<Play size={14} aria-hidden="true" />
				{submit.submitting ? 'Queuing…' : 'Generate'}
			</Button>
		</div>
	</form>
</Card>

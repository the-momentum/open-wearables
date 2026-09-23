<script lang="ts">
	import Eye from '@lucide/svelte/icons/eye';
	import EyeOff from '@lucide/svelte/icons/eye-off';
	import TextField from './TextField.svelte';

	let {
		name,
		label,
		autocomplete,
		placeholder
	}: {
		name: string;
		label: string;
		autocomplete: 'current-password' | 'new-password';
		placeholder?: string;
	} = $props();

	let shown = $state(false);
</script>

<TextField
	{name}
	{label}
	{autocomplete}
	{placeholder}
	type={shown ? 'text' : 'password'}
	required
	class="pr-11"
>
	{#snippet trailing()}
		<!-- Typing a password you cannot see is how the confirmation gets it wrong. -->
		<button
			type="button"
			onclick={() => (shown = !shown)}
			aria-label={shown ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
			class="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground
				transition-colors hover:text-foreground"
		>
			{#if shown}
				<EyeOff size={16} aria-hidden="true" />
			{:else}
				<Eye size={16} aria-hidden="true" />
			{/if}
		</button>
	{/snippet}
</TextField>

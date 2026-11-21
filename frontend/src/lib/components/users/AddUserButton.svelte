<script lang="ts">
	import UserPlus from '@lucide/svelte/icons/user-plus';
	import Button from '$lib/components/ui/Button.svelte';
	import { ICON } from '$lib/components/ui/icon';

	let { onclick }: { onclick: () => void } = $props();
</script>

<Button {onclick} class="w-full">
	<UserPlus size={ICON.sm} aria-hidden="true" />
	Add user
</Button>

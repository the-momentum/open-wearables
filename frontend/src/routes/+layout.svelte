<script lang="ts">
	import '../app.css';
	import { setLucideProps } from '@lucide/svelte';

	// The design's icons are 1px on screen at every size.
	setLucideProps({ strokeWidth: 1, absoluteStrokeWidth: true });

	let { children } = $props();
</script>

<svelte:head>
	<title>Ren — Open Wearables Platform</title>
</svelte:head>

{@render children()}

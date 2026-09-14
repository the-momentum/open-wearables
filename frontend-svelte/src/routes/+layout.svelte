<script lang="ts">
	import '../app.css';

	let { children } = $props();
</script>

<svelte:head>
	<title>Open Wearables</title>
</svelte:head>

{@render children()}

<script lang="ts">
	import { cn } from '$lib/utils/cn';
	import { TONE, type Tone } from './tone';

	let { code, tone }: { code: number | null; tone: Tone } = $props();
</script>

<!-- An HTTP status is read digit by digit, so it is set in mono and wears the
     tone itself rather than sitting in grey beside a dot that repeats it. -->
<span
	class={cn(
		'inline-flex shrink-0 rounded-md px-2 py-0.5 font-mono text-sm leading-tagline tabular-nums',
		TONE[tone]
	)}
>
	{code || '-'}
</span>

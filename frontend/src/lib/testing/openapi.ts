import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

type Spec = {
	paths: Record<string, unknown>;
	components: { schemas: Record<string, { enum?: string[] }> };
};

export const openapi = (): Spec =>
	JSON.parse(readFileSync(resolve(process.cwd(), '../docs/openapi.json'), 'utf8'));

export const openapiEnum = (schema: string): string[] =>
	openapi().components.schemas[schema]?.enum ?? [];

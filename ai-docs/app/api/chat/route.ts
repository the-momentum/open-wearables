import { anthropic } from "@ai-sdk/anthropic";
import { streamText, tool } from "ai";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { z } from "zod";

function jsonSchemaToZod(schema: Record<string, unknown>): z.ZodType {
  const props = (schema.properties ?? {}) as Record<string, { type?: string; description?: string }>;
  const required = (schema.required ?? []) as string[];
  const shape: Record<string, z.ZodType> = {};

  for (const [key, prop] of Object.entries(props)) {
    let field: z.ZodType = z.string();
    if (prop.description) field = (field as z.ZodString).describe(prop.description);
    if (!required.includes(key)) field = field.optional();
    shape[key] = field;
  }

  return z.object(shape);
}

export async function POST(req: Request) {
  const { messages } = await req.json();

  const transport = new StreamableHTTPClientTransport(
    new URL("https://docs.openwearables.io/mcp"),
  );
  const client = new Client({ name: "ai-docs", version: "1.0.0" });
  await client.connect(transport);

  try {
    const { tools: mcpTools } = await client.listTools();

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const tools: Record<string, any> = {};
    for (const t of mcpTools) {
      tools[t.name] = tool({
        description: t.description ?? "",
        parameters: jsonSchemaToZod(t.inputSchema as Record<string, unknown>),
        execute: async (args) => {
          const result = await client.callTool({ name: t.name, arguments: args });
          const content = result.content as Array<{ type: string; text?: string }>;
          return content
            .filter((c) => c.type === "text" && c.text)
            .map((c) => c.text)
            .join("\n");
        },
      });
    }

    const result = streamText({
      model: anthropic("claude-sonnet-4-20250514"),
      system: `You are a helpful documentation assistant for Open Wearables — an open-source health/wearable data aggregation platform.

Use the SearchOpenWearables tool to find relevant documentation before answering. Always ground your answers in the actual docs content.

Guidelines:
- Be concise and direct
- Include links to relevant documentation pages when available
- If you can't find an answer in the docs, say so honestly
- Format responses with markdown for readability`,
      messages,
      tools,
      maxSteps: 3,
      onFinish: async () => {
        await client.close();
      },
    });

    return result.toDataStreamResponse();
  } catch (error) {
    await client.close();
    throw error;
  }
}

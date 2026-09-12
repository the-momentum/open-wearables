# Build stage
FROM oven/bun:1.4-alpine AS builder

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

ENV NODE_ENV=production
RUN bun run build

# Production stage
FROM oven/bun:1.4-alpine

WORKDIR /app

# adapter-node emits the server into build/ but leaves runtime dependencies to
# us, so install the production subset alongside it.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

COPY --from=builder /app/build ./build

# PORT/HOST are read by adapter-node at boot. PUBLIC_API_URL is deliberately
# not baked in: it is resolved per-container at runtime, so one image can point
# at any backend.
ENV NODE_ENV=production
ENV PORT=3001
ENV HOST=0.0.0.0

EXPOSE 3001

CMD ["bun", "./build/index.js"]

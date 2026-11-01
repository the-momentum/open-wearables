# Build stage
FROM public.ecr.aws/docker/library/node:22-alpine AS builder

# Bun is not an official Docker Hub image, so oven/bun cannot be pulled from
# the ECR Public mirror inside the VPC; install it via npm at build time.
RUN npm install -g bun@1.4

WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .

ENV NODE_ENV=production
RUN bun run build

# Production stage
FROM public.ecr.aws/docker/library/node:22-alpine

RUN npm install -g bun@1.4

WORKDIR /app

# adapter-node emits the server into build/ but leaves runtime dependencies to
# us, so install the production subset alongside it.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --production

COPY --from=builder /app/build ./build

# PORT/HOST are read by adapter-node at boot. VITE_API_URL is deliberately
# not baked in: it is resolved per-container at runtime, so one image can point
# at any backend.
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

EXPOSE 3000

CMD ["bun", "./build/index.js"]

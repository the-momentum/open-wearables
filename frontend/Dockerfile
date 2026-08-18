# Build stage
FROM node:22-alpine AS builder

# Install pnpm
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate

WORKDIR /app

# Build arguments for environment variables
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

# Copy package files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source files
COPY . .

# Build the application in production mode
ENV NODE_ENV=production
RUN pnpm run build

# Production stage
FROM node:22-alpine

WORKDIR /app
# Copy the Nitro build output (server + static public assets) from the builder
COPY --from=builder /app/.output ./.output

# Expose port
EXPOSE 3000

# Set the port for Nitro
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0

# Run the Nitro server
CMD ["node", ".output/server/index.mjs"]

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

# Build the application
RUN pnpm run build

# Determine build output directory and prepare it for copying
# Nitro outputs to .output/public, Vite outputs to dist
RUN if [ -d /app/.output/public ]; then \
      echo "Using Nitro output: .output/public"; \
      cp -r /app/.output/public /app/build-output; \
    elif [ -d /app/dist ]; then \
      echo "Using Vite output: dist"; \
      cp -r /app/dist /app/build-output; \
    else \
      echo "ERROR: No build output found!"; \
      ls -la /app/; \
      exit 1; \
    fi

# Production stage
FROM node:22-alpine

WORKDIR /app

# Copy built output from builder (Nitro SSR bundle)
COPY --from=builder /app/.output ./.output

# Expose port
EXPOSE 3000

# Set environment variables for Nitro server
# Nitro 3.x uses NITRO_HOST and NITRO_PORT as primary variables
ENV NODE_ENV=production
ENV PORT=3000
ENV HOST=0.0.0.0
ENV NITRO_PORT=3000
ENV NITRO_HOST=0.0.0.0

# Run the Nitro server
CMD ["node", ".output/server/index.mjs"]

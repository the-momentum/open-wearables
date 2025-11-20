# Build stage
FROM node:22-alpine AS builder

# Install pnpm
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate

WORKDIR /app

# Build arguments for environment variables
ENV VITE_API_URL=http://localhost:8000

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
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/build-output /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

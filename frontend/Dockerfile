# Stage 1: Build
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (cache layer)
COPY package.json package-lock.json* ./
RUN npm install

# Copy source and build
COPY . .
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine

# Copy custom nginx config (overwrite any existing)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Remove any other default configs that might conflict
RUN rm -f /etc/nginx/conf.d/default.conf.bak 2>/dev/null; \
    rm -f /etc/nginx/conf.d/other.conf 2>/dev/null; true

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

# ============================================================
# Stage 1 — builder
#   Builds the React/Vite app into a static dist/ folder
# ============================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifest files first for cache-efficient installs
COPY package.json package-lock.json ./

RUN npm ci

# Copy the rest of the frontend source
COPY . .

# Production build (runs: tsc -b && vite build)
RUN npm run build


# ============================================================
# Stage 2 — runtime
#   Serves the built static files via Nginx
# ============================================================
FROM nginx:1.27-alpine AS runtime

# Remove default Nginx welcome config
RUN rm /etc/nginx/conf.d/default.conf

# Copy our custom Nginx config
COPY nginx.conf /etc/nginx/conf.d/app.conf

# Copy built frontend assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx runs as non-root by default on port 8080 in official images,
# but we'll use port 80 with the standard root user (Nginx drops
# privileges to 'nginx' user after binding the port).
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

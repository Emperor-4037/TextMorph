# Stage 1 — Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE=http://localhost:8000
ARG VITE_DEMO_TOKEN=demo-token
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_DEMO_TOKEN=$VITE_DEMO_TOKEN
RUN npm run build

# Stage 2 — Serve via Nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
# SPA routing and API reverse proxy
RUN echo 'server { \
    listen 80; \
    location /api/ { proxy_pass http://gateway:8000/api/; proxy_set_header Host $host; proxy_set_header X-Real-IP $remote_addr; } \
    location /health { proxy_pass http://gateway:8000/health; } \
    location /readiness { proxy_pass http://gateway:8000/readiness; } \
    location / { root /usr/share/nginx/html; try_files $uri /index.html; } \
}' > /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

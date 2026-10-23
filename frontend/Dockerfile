# Build: Next.js static export. Serve: nginx + reverse-proxy /users|/booking to gateway.
FROM node:22-alpine AS builder

WORKDIR /app

COPY ./frontend/package.json ./frontend/pnpm-lock.yaml ./frontend/pnpm-workspace.yaml ./
RUN npm install -g pnpm@10 \
    && pnpm install --frozen-lockfile

COPY ./frontend .
RUN pnpm build

FROM nginx:1.27-alpine

COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/out /usr/share/nginx/html

EXPOSE 80

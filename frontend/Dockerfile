# Build: Next.js static export. Serve: nginx + reverse-proxy /users|/booking to gateway.
FROM node:22-alpine AS builder

WORKDIR /app

# 2GIS MapGL key is baked into the static export (client-side by design).
ARG NEXT_PUBLIC_2GIS_MAP_KEY=""
ENV NEXT_PUBLIC_2GIS_MAP_KEY=$NEXT_PUBLIC_2GIS_MAP_KEY

COPY ./frontend/package.json ./frontend/pnpm-lock.yaml ./frontend/pnpm-workspace.yaml ./
RUN npm install -g pnpm@10 \
    && pnpm install --frozen-lockfile

COPY ./frontend .
RUN pnpm build

FROM nginx:1.27-alpine

# The stock http-level access_log would duplicate every request in the old
# combined format (including query strings). Use only the JSON server log.
RUN sed -i '/access_log/d' /etc/nginx/nginx.conf

COPY ./frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/out /usr/share/nginx/html

EXPOSE 80

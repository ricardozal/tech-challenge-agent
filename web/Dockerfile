# Build context: repository root (see docker-compose.yml).
FROM node:24-alpine AS build
WORKDIR /web
ARG VITE_AGENT_URL=http://localhost:8001
ARG VITE_ACTIONS_URL=http://localhost:8000
ENV VITE_AGENT_URL=$VITE_AGENT_URL \
    VITE_ACTIONS_URL=$VITE_ACTIONS_URL
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
COPY fixtures/documents/*.png ./public/documents/
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080

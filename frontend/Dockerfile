# =============================================================================
# frontend/Dockerfile -- SecureCode AI web dashboard. Multi-stage: build the
# Vite/React app, then serve the static output with nginx.
#
#   docker build -f frontend/Dockerfile -t securecode-ai-frontend ./frontend
# =============================================================================

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

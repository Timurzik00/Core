# --- Build stage ---
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

# --- Serve stage ---
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Кладём шаблон в /etc/nginx/templates/ — nginx сам подставит переменные
# окружения через envsubst при старте контейнера.
COPY default.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 80

FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_BASE=/filamentfinder/
ARG VITE_ADMIN_API_KEY=

ENV VITE_BASE=$VITE_BASE
ENV VITE_ADMIN_API_KEY=$VITE_ADMIN_API_KEY

COPY package*.json ./
RUN npm install --include=dev

COPY . .

RUN npx vite build

FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist /usr/share/nginx/html
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3030

ENTRYPOINT ["/entrypoint.sh"]

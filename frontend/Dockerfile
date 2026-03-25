FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --include=dev

COPY . .

EXPOSE 3030

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3030", "--strictPort"]

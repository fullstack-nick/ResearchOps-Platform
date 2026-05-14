FROM node:24.15.0

WORKDIR /app

RUN npm install -g npm@11.14.1

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY index.html ./
COPY tsconfig*.json ./
COPY vite.config.ts ./
COPY eslint.config.js ./
COPY playwright.config.ts ./
COPY src ./src
COPY e2e ./e2e

EXPOSE 5173

CMD ["npm", "run", "dev"]

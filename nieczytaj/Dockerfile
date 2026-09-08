# nieczytaj.pl / LIESNICHT — single-file, dependency-free Node 22 app.
# Self-contained build for Railway services rooted in nieczytaj/ (root
# directory = nieczytaj): nothing from the repo root is needed.
FROM node:22-slim

WORKDIR /app
ENV NODE_ENV=production

COPY package.json server.js ./

# Railway injects PORT; server.js falls back to 8080 (the domains' target port).
EXPOSE 8080
CMD ["node", "server.js"]

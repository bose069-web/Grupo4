# ---------------------------------------------------------------------------
# Frontend MÍNIMO de prueba (nginx + HTML estático).
# Sirve para comprobar que la red frontend -> api funciona.
# DAW/DAM: sustituid index.html (o este Dockerfile entero) por vuestro frontend.
# Mantened el proxy /api/ de nginx.conf o configurad CORS en la API.
# ---------------------------------------------------------------------------
FROM nginx:stable-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

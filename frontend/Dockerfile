FROM nginx:1.27-alpine

# nginx:alpine's entrypoint auto-runs envsubst on any *.template file in
# /etc/nginx/templates/, writing the result to /etc/nginx/conf.d/ on startup.
# (Kept for local docker-compose use / same-domain proxying; not required
# when frontend and backend are deployed as separate Render services with
# CORS enabled - see API_BASE_URL below.)
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template

COPY config.template.js /etc/nginx/config.template.js
COPY 40-generate-frontend-config.sh /docker-entrypoint.d/40-generate-frontend-config.sh
RUN chmod +x /docker-entrypoint.d/40-generate-frontend-config.sh
COPY index.html style.css script.js /usr/share/nginx/html/

# The backend is a separate Render service at its own URL. Set this on the
# frontend service's Render env vars to the backend's full public URL, e.g.:
#   API_BASE_URL=https://ai-resume-checker-backend-12el.onrender.com
# Backend has CORS allow_origins=["*"], so direct cross-origin calls work.
ENV API_BASE_URL=""
ENV BACKEND_HOST=ai-resume-checker-backend-12el.onrender.com

EXPOSE 80

// Generated at container startup from config.template.js via envsubst.
// Lets the frontend's API base URL be set with an env var (API_BASE_URL)
// instead of being hardcoded into script.js.
//
// Leave API_BASE_URL unset/empty to keep using the nginx proxy at /api
// (see templates/default.conf.template + BACKEND_HOST).
window.APP_CONFIG = {
  apiBaseUrl: "${API_BASE_URL}"
};

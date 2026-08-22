# Zorbeck — landing page collecting signups for property deal alerts (email + city + budget → SIGNUP_WEBHOOK_URL).
# Deploy: separate Railway service in this repo with Railway Root Directory = `zorbeck`; start command comes from the Procfile.
# Env: `SIGNUP_WEBHOOK_URL` (optional — without it signups are only logged).
#      Default target: https://startend.app.n8n.cloud/webhook/zorbeck-lead

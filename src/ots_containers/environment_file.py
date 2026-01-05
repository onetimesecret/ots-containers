CONTAINER_TEMPLATE = """\
# /etc/default/onetimesecret

##
# Onetime Secret - Environment Variables (updated YY-MM-DD)
#
# Usage:
#
#   $ vi /etc/default/onetimesecret
#

# Stored with podman secrets
#STRIPE_API_KEY=
#STRIPE_WEBHOOK_SIGNING_SECRET=
#SECRET=
#SESSION_SECRET=
#HMAC_SECRET=
#SMTP_PASSWORD=

# Connections
AUTH_DATABASE_URL=
AUTH_DATABASE_URL_MIGRATIONS=
RABBITMQ_URL=
REDIS_URL=

# Mail
SMTP_USERNAME=lettermint
SMTP_HOST=smtp.lettermint.co
SMTP_PORT=587
SMTP_AUTH=login
SMTP_TLS=true

# Integrations
CLUSTER_TYPE=

SENTRY_DSN_BACKEND=
SENTRY_DSN_FRONTEND=

PUBLIC_STRIPE_API_KEY=

# Core Settings
HOST=
COLONEL=EMAILADDRESS


#
# ONLY FLAGS AND SETTINGS BEYOND THIS POINT
#

AUTHENTICATION_MODE=full

SSL=true
STDOUT_SYNC=false
ONETIME_DEBUG=false
RACK_ENV=production

DEFAULT_LOG_LEVEL=debug

# Logging Configuration
# Set to 'false' to disable request logging
LOG_HTTP_REQUESTS=true
LOG_HTTP_REQUESTS_LEVEL=debug
LOG_HTTP_CAPTURE=debug

JOBS_ENABLED=true

# Authentication settings
AUTH_ENABLED=true
AUTH_SIGNUP=true
AUTH_SIGNIN=true
AUTH_AUTOVERIFY=false

# Email settings
EMAILER_MODE=smtp
EMAILER_REGION=
FROM_EMAIL=
FROMEMAIL=
FROMNAME=
FROM=

VERIFIER_EMAIL=
VERIFIER_DOMAIN=

# One of: DefaultLogo.vue, LegacyLogo.vue, OnetimeSecretLogo.vue
LOGO_URL=

# Footer Links
FOOTER_LINKS=
TERMS_URL=
TERMS_EXTERNAL=
PRIVACY_URL=
PRIVACY_EXTERNAL=
STATUS_URL=
STATUS_EXTERNAL=
ABOUT_URL=
ABOUT_EXTERNAL=
CONTACT_URL=

# Feature flags
REGIONS_ENABLED=
JURISDICTION=
DOMAINS_ENABLED=
DEFAULT_DOMAIN=
I18N_ENABLED=
I18N_DEFAULT_LOCALE=

# Monitoring and Diagnostics
DIAGNOSTICS_ENABLED=
SENTRY_VUE_TRACK_COMPONENTS=
SENTRY_SAMPLE_RATE
SENTRY_MAX_BREADCRUMBS
SENTRY_LOG_ERRORS=
HEADER_PREFIX=

# # Homepage Mode
# # Controls which homepage experience to show based on IP address or headers
# # Mode: 'internal' or 'external' or blank
# UI_HOMEPAGE_MODE=
# # Comma-separated list of CIDR ranges (e.g., "10.0.0.0/8,192.168.0.0/16")
# UI_HOMEPAGE_MATCHING_CIDRS=
# # HTTP header name to check as fallback (default: O-Homepage-Mode)
# UI_HOMEPAGE_MODE_HEADER=
# # Default mode to apply when IP doesn't match CIDRs: 'internal', 'external', or blank (nil)
# UI_HOMEPAGE_DEFAULT_MODE=
# # Number of trusted proxies (0=direct, 1=single proxy, 2+=multiple proxies)
# UI_HOMEPAGE_TRUSTED_PROXY_DEPTH=
# # Which header to use for IP: X-Forwarded-For, Forwarded, or Both
# UI_HOMEPAGE_TRUSTED_IP_HEADER=
"""

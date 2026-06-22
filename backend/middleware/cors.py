"""
CORS Configuration Middleware

Configures Cross-Origin Resource Sharing for the Android WebView
and development clients.
"""

from utils.config import settings

# CORS is configured directly in main.py via FastAPI's CORSMiddleware.
# This file exists for documentation and to keep CORS-related config
# centralized.

# The actual origins list is defined in utils/config.py under
# settings.cors_origins. For Android Capacitor WebView:
#   - capacitor://localhost
#   - http://localhost
#   - http://localhost:8100  (Capacitor dev server)
#   - http://localhost:3000  (React dev server)
#
# In production, restrict to specific origins instead of using "*".

CORS_CONFIG = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "X-Device-ID",
    ],
    "expose_headers": [
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
    ],
    "max_age": 600,  # Preflight cache: 10 minutes
}

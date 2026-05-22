import os
from dotenv import load_dotenv

load_dotenv()

# Facebook
FB_TOKENS = [t.strip() for t in os.getenv("FB_TOKENS", "").split(",") if t.strip()]

# PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://adspy:adspy@localhost:5432/adspy")

# Elasticsearch
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# S3 / Cloudflare R2
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_BUCKET = os.getenv("S3_BUCKET", "adspy-creatives")
S3_PUBLIC_URL = os.getenv("S3_PUBLIC_URL", "")

# Proxy
PROXY_URL = os.getenv("PROXY_URL", "")

# Anthropic (Vision classification)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Gemini (free tier classification)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Auth
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

import os
import re
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

def sanitize_db_url(url: str) -> str:
    """Ensure database URL is properly formatted for SQLAlchemy with Supabase pooler compatibility."""
    if not url:
        return ""
    
    # Fix unencoded '@' in password if present: postgresql://user:pass@word@host:port/db
    # Look for scheme://user:pass@host pattern where pass contains unescaped @
    match = re.match(r'^(postgresql(?:[+\w]+)?://)([^:]+):([^@]+)@(.+)$', url)
    if match:
        prefix, user, raw_pass, rest = match.groups()
        # If there's an extra @ in rest before the host:port/db, fix encoding
        if "@" in rest and not rest.startswith("aws-") and not rest.startswith("db."):
            pass_parts = raw_pass.split("@") + rest.split("@")[:-1]
            actual_pass = "@".join(pass_parts)
            actual_host = rest.split("@")[-1]
            url = f"{prefix}{user}:{quote_plus(actual_pass)}@{actual_host}"

    # Clean pgbouncer parameter which psycopg2 does not support directly
    if "?" in url and "sqlite" not in url:
        base_url, query_params = url.split("?", 1)
        params = [p for p in query_params.split("&") if not p.startswith("pgbouncer")]
        url = base_url + ("?" + "&".join(params) if params else "")

    return url

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Supply Chain AI Decision-Intelligence")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Supabase & Database Configuration
    RAW_DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres.cugiwyrgfptehvkexejg:StrongPassword%40123..@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    )
    DATABASE_URL: str = sanitize_db_url(RAW_DATABASE_URL)
    
    RAW_DIRECT_URL: str = os.getenv("DIRECT_URL", "")
    DIRECT_URL: str = sanitize_db_url(RAW_DIRECT_URL) if RAW_DIRECT_URL else DATABASE_URL
    
    # Supabase Keys (handles both SUPABASE_ and SUPBASE_ spelling in .env)
    SUPABASE_ANON_KEY: str = (
        os.getenv("SUPABASE_ANON_KEY") or 
        os.getenv("SUPBASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN1Z2l3eXJnZnB0ZWh2a2V4ZWpnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc4MDY2MjEsImV4cCI6MjEwMzM4MjYyMX0.70SI4gNtg_QGo-x8mivn1_u45bZ8wBVtjc5pD7BORAQ")
    )
    SUPABASE_SERVICE_ROLE_KEY: str = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or 
        os.getenv("SUPBASE_service_role") or 
        os.getenv("SUPBASE_SERVICE_ROLE", "")
    )
    SUPABASE_SECRET_KEY: str = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPBASE_SECRET_KEY", "")
    
    # Derive Supabase HTTPS URL from env or DATABASE_URL reference
    SUPABASE_URL: str = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", "")
    
    def __init__(self):
        if not self.SUPABASE_URL:
            # Extract Supabase reference string from DATABASE_URL (e.g. postgres.cugiwyrgfptehvkexejg -> cugiwyrgfptehvkexejg)
            match = re.search(r'postgres\.([a-z0-9]+)@', self.DATABASE_URL) or re.search(r'([a-z0-9]{20})', self.DATABASE_URL)
            if match:
                ref = match.group(1)
                self.SUPABASE_URL = f"https://{ref}.supabase.co"
            else:
                self.SUPABASE_URL = "https://cugiwyrgfptehvkexejg.supabase.co"
                
    # LLM API Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "openai").lower() # openai, claude, gemini, rule_based

settings = Settings()


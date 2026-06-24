from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
    enabled=settings.ENVIRONMENT != "test"
)

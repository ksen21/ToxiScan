"""
services/rate_limit.py — shared slowapi Limiter instance.

Lives in its own module (not main.py) so routers/scan.py can import and
apply it to individual routes without a circular import back to main.py
(which itself needs to import the scan router).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

"""Auth router stub.

Day 1: empty router; helpers in `app/auth.py` ready for use.
Day 2: register / login / me endpoints (email + password + JWT).
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/auth", tags=["auth"])

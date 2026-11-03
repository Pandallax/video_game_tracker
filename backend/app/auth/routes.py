import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest, request: Request):
    username_ok = secrets.compare_digest(body.username, settings.app_username)
    password_ok = secrets.compare_digest(body.password, settings.app_password)
    if not (username_ok and password_ok):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    request.session["authenticated"] = True
    return {"authenticated": True}


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}


@router.get("/me")
def me(request: Request):
    if request.session.get("authenticated"):
        return {"authenticated": True}
    raise HTTPException(status_code=401, detail="Not authenticated")

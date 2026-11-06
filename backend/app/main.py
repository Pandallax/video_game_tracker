from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth.routes import router as auth_router
from app.config import settings
from app.routes.copies import router as copies_router
from app.routes.games import router as games_router
from app.routes.imports import router as imports_router
from app.routes.sales import router as sales_router
from app.routes.stats import router as stats_router

app = FastAPI(title="Video Game Tracker API")

app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax", https_only=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(games_router)
app.include_router(copies_router)
app.include_router(sales_router)
app.include_router(stats_router)
app.include_router(imports_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

import asyncio
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.future import select

from audioscribetranslate.core.files import create_uploaded_files_structure
from audioscribetranslate.db.session import AsyncSessionLocal
from audioscribetranslate.db.utils import create_admin_if_not_exists
from audioscribetranslate.models.user import User
from audioscribetranslate.routers import (
    audio_file,
    example,
    summary,
    transcript,
    translation,
    user,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # --- startup ---
    admin_name = os.getenv("ADMIN_NAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    await create_admin_if_not_exists(admin_name, admin_password)

    # --- create uploaded_files/{model}/{user} structure ---
    models = os.getenv("WHISPER_MODELS", "base,small,medium,large").split(",")
    models = [m.strip() for m in models if m.strip()]
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User.name))
        user_names = [row[0] for row in result.all()]
    create_uploaded_files_structure(models, user_names)

    yield
    # --- shutdown ---


app = FastAPI(title="AudioScribeTranslate API", lifespan=lifespan)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "AudioScribeTranslate backend is running!"}


app.include_router(example.router)
app.include_router(user.router)
app.include_router(audio_file.router)
app.include_router(transcript.router)
app.include_router(translation.router)
app.include_router(summary.router)

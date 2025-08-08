import os

from sqlalchemy.future import select

from audioscribetranslate.models.user import User

from .session import AsyncSessionLocal


async def create_admin_if_not_exists(admin_name: str, admin_password: str) -> None:
    """
    Создаёт администратора, если его нет в базе.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.name == admin_name))
        admin = result.scalar_one_or_none()
        if not admin:
            admin = User(
                name=admin_name, hashed_password=admin_password, is_active=1, is_admin=1
            )
            session.add(admin)
            await session.commit()
            print(f"[INIT] Admin user '{admin_name}' created.")
        else:
            print(f"[INIT] Admin user '{admin_name}' already exists.")

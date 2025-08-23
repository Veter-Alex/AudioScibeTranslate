import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from audioscribetranslate.models.user import User

from .session import AsyncSessionLocal


async def create_admin_if_not_exists(admin_name: str, admin_password: str, session: AsyncSession) -> None:
    """
    Создаёт администратора, если его нет в базе.

    Args:
        admin_name (str): Имя администратора.
        admin_password (str): Хэш пароля администратора.

    Returns:
        None

    Example:
        await create_admin_if_not_exists('admin', 'hashed_pass')

    Warning:
        Пароль должен быть предварительно захеширован!
    """
    if not admin_name:
        print(f"[INIT] Admin user name is empty, creation skipped.")
        return
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

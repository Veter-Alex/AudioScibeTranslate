from typing import Any

from sqlalchemy import Column, Integer, String

from .base import Base


class User(Base):
    """
    Модель пользователя системы.

    Attributes:
        id (int): Уникальный идентификатор пользователя.
        name (str): Имя пользователя (уникальное).
        hashed_password (str): Хэш пароля пользователя.
        is_active (int): Активен ли пользователь (1 — да, 0 — нет).
        is_admin (int): Является ли пользователь администратором (1 — да, 0 — нет).

    Example:
        user = User(name='alice', hashed_password='...', is_admin=1)

    Pitfalls:
        - Пароль должен быть захеширован.
        - Имя пользователя должно быть уникальным.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String, unique=True, index=True, nullable=False
    )  # Имя пользователя (уникальное)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1, server_default="1", nullable=False)
    is_admin = Column(
        Integer, default=0, server_default="0", nullable=False
    )  # Является ли пользователь администратором (0/1)

    def __init__(self, **kwargs: Any) -> None:
        if "is_active" not in kwargs:
            kwargs["is_active"] = 1
        if "is_admin" not in kwargs:
            kwargs["is_admin"] = 0
        super().__init__(**kwargs)
        super().__init__(**kwargs)

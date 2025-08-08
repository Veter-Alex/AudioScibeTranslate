from sqlalchemy import Column, Integer, String

from .base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(
        String, unique=True, index=True, nullable=False
    )  # Имя пользователя (уникальное)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    is_admin = Column(
        Integer, default=0
    )  # Является ли пользователь администратором (0/1)

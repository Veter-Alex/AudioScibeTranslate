from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Базовый класс для всех ORM моделей проекта.

    Используется для наследования всеми моделями SQLAlchemy.

    Example:
        class User(Base):
            ...
    """
    pass
    pass

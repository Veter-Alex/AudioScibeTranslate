def get_uploaded_files_dir() -> str:
    """
    Возвращает абсолютный путь к папке uploaded_files в корне проекта.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../uploaded_files")
    )


import os
from typing import Sequence


def create_uploaded_files_structure(
    models: Sequence[str], user_names: Sequence[str], base_dir: str | None = None
) -> None:
    """
    Создаёт структуру uploaded_files/{model}/{user} для хранения аудиофайлов.
    :param models: список названий моделей транскрибирования
    :param user_names: список имён пользователей
    :param base_dir: путь к папке uploaded_files (по умолчанию autodetect)
    """
    if base_dir is None:
        base_dir = get_uploaded_files_dir()
    os.makedirs(base_dir, exist_ok=True)
    for model in models:
        model_dir = os.path.join(base_dir, model)
        os.makedirs(model_dir, exist_ok=True)
        for user in user_names:
            user_dir = os.path.join(model_dir, user)
            os.makedirs(user_dir, exist_ok=True)
    print(
        f"[INIT] uploaded_files structure created for models: {models} and users: {user_names}"
    )
    print(
        f"[INIT] uploaded_files structure created for models: {models} and users: {user_names}"
    )

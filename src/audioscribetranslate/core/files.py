def get_uploaded_files_dir() -> str:
    """
    Возвращает абсолютный путь к папке uploaded_files в корне проекта.

    Returns:
        str: Абсолютный путь к директории uploaded_files.

    Example:
        >>> get_uploaded_files_dir()
        'C:/project/uploaded_files'

    Note:
        Папка uploaded_files должна существовать или быть создана вручную.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../uploaded_files")
    )


import os  # Модуль для работы с файловой системой и путями
from typing import Sequence


def create_uploaded_files_structure(
    models: Sequence[str], user_names: Sequence[str], base_dir: str | None = None
) -> None:
    """
    Создаёт структуру uploaded_files/{model}/{user} для хранения аудиофайлов.

    Args:
        models (Sequence[str]): Список названий моделей транскрибирования (например, ['base', 'small']).
        user_names (Sequence[str]): Список имён пользователей.
        base_dir (str | None): Путь к папке uploaded_files. Если None, определяется автоматически.

    Returns:
        None

    Example:
        >>> create_uploaded_files_structure(['base', 'small'], ['alice', 'bob'])
        # Создаст директории uploaded_files/base/alice, uploaded_files/base/bob, ...

    Warning:
        Если папка уже существует, структура будет дополнена, но существующие файлы не затронутся.

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

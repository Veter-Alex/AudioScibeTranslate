"""
Скрипт для инспекции новых таблиц transcripts, translations, summaries в базе данных.

Показывает:
- Список всех таблиц
- Колонки для transcripts, translations, summaries
- Версию Alembic

Usage:
    python inspect_new_tables.py

Pitfalls:
- Требует настроенного подключения к базе
- Не подходит для production-аналитики
"""

from sqlalchemy import create_engine, text

from audioscribetranslate.core.config import get_settings


def main() -> None:
    """
    Выводит структуру и колонки новых таблиц transcripts, translations, summaries.

    Steps:
        - Получает список всех таблиц
        - Показывает колонки для ключевых таблиц
        - Показывает версию Alembic

    Pitfalls:
        - Скрипт только для отладки и анализа
    """
    s = get_settings()
    engine = create_engine(s.sync_database_url)
    with engine.connect() as c:
        tables = c.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1"
            )
        ).fetchall()
        print("tables:", [t[0] for t in tables])
        for name in ("transcripts", "translations", "summaries"):
            cols = c.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name=:n"
                ),
                {"n": name},
            ).fetchall()
            print(name, "cols:", [c_[0] for c_ in cols])
        ver = c.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        print("alembic_version:", [v[0] for v in ver])

if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()

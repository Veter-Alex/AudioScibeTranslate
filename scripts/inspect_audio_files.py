from sqlalchemy import create_engine, text

from audioscribetranslate.core.config import get_settings


def main():
    settings = get_settings()
    engine = create_engine(settings.sync_database_url)
    with engine.connect() as conn:
        cols = conn.execute(
            text(
                """
            SELECT column_name FROM information_schema.columns
            WHERE table_name='audio_files' ORDER BY ordinal_position
        """
            )
        ).fetchall()
        print("audio_files columns:", [c[0] for c in cols])
        rows = conn.execute(
            text("SELECT id, filename, storage_path FROM audio_files LIMIT 5")
        )
        print("sample rows:")
        for r in rows:
            print(dict(r._mapping))
        ver = conn.execute(text("SELECT version_num FROM alembic_version"))
        print("alembic version table:", [v[0] for v in ver])


if __name__ == "__main__":
    main()
    main()

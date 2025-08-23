#!/usr/bin/env python3
"""
Скрипт очистки тестовых данных из базы данных.
"""

import asyncio
from sqlalchemy import text
from src.audioscribetranslate.db.session import AsyncSessionLocal


async def cleanup_test_data():
    """Очищает тестовые данные из базы данных."""
    print('🧹 Очистка тестовых данных из базы данных...')
    
    async with AsyncSessionLocal() as db:
        try:
            # Удаляем только тестовые аудиофайлы (каскадное удаление сработает автоматически)
            result = await db.execute(
                text("DELETE FROM audio_files WHERE filename LIKE '%test_chain_audio.wav'")
            )
            deleted_audio = result.rowcount
            
            await db.commit()
            print(f'✅ Удалено {deleted_audio} тестовых аудиофайлов и связанных записей')
            
        except Exception as e:
            print(f'❌ Ошибка при очистке: {e}')
            await db.rollback()
    
    print('🎉 Очистка завершена!')


if __name__ == "__main__":
    asyncio.run(cleanup_test_data())

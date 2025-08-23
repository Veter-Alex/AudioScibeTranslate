import asyncio
import io

from httpx import ASGITransport, AsyncClient

from src.audioscribetranslate.main import app


async def debug_audio_files_endpoint():
    """Минимальный тест для диагностики проблемы с /audio_files/"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            # Попробуем сделать POST запрос
            resp = await client.post(
                "/audio_files/",
                files={"file": ("test.mp3", io.BytesIO(b"test"), "audio/mpeg")},
                data={"whisper_model": "base", "user_id": "1"},
            )
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")
            
            # Проверим схему OpenAPI
            openapi_resp = await client.get("/openapi.json")
            if openapi_resp.status_code == 200:
                openapi = openapi_resp.json()
                audio_files_post = openapi.get("paths", {}).get("/audio_files/", {}).get("post", {})
                print("\nOpenAPI schema for POST /audio_files/:")
                print(f"Parameters: {audio_files_post.get('parameters', [])}")
                if 'requestBody' in audio_files_post:
                    print(f"Request body: {audio_files_post['requestBody']}")
                    
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_audio_files_endpoint())

if __name__ == "__main__":
    asyncio.run(debug_audio_files_endpoint())

# __init__.py
#
# Маркер пакета для модуля моделей ORM.
#
# Example:
#     from audioscribetranslate.models import user, audio_file

from .audio_file import AudioFile
from .summary import Summary
from .transcript import Transcript
from .translation import Translation

# Импортируем все модели для правильной работы relationships
from .user import User

__all__ = ["User", "AudioFile", "Transcript", "Translation", "Summary"]
__all__ = ["User", "AudioFile", "Transcript", "Translation", "Summary"]

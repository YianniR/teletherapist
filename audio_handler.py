import whisper
import tempfile
import os
import logging
from telegram import File
from config import WHISPER_MODEL

logger = logging.getLogger(__name__)

# Load Whisper model once at startup
logger.info(f"Loading Whisper model: {WHISPER_MODEL}")
model = whisper.load_model(WHISPER_MODEL)
logger.info("Whisper model loaded successfully")

async def process_voice_note(voice_note: File) -> str:
    """
    Download voice note and transcribe it using Whisper
    """
    logger.info("Starting voice note processing")
    
    # Create temp directory for audio file
    with tempfile.TemporaryDirectory() as temp_dir:
        # Download voice note
        file_path = os.path.join(temp_dir, "voice_note.ogg")
        logger.debug(f"Downloading voice note to: {file_path}")
        
        await voice_note.download_to_drive(file_path)
        logger.info(f"Voice note downloaded successfully. File size: {os.path.getsize(file_path)} bytes")
        
        # Transcribe with Whisper
        logger.debug("Starting Whisper transcription")
        result = model.transcribe(file_path)
        
        transcription = result["text"].strip()
        logger.info(f"Transcription completed. Result length: {len(transcription)} characters")
        
        return transcription 
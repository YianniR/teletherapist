import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import TELEGRAM_TOKEN, ALLOWED_USER_ID
from audio_handler import process_voice_note
from claude_client import get_claude_response
from database import ConversationDB

# Reduce noise from other loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore.http11').setLevel(logging.WARNING)
logging.getLogger('httpcore.connection').setLevel(logging.WARNING)

# Configure our logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    force=True
)
logger = logging.getLogger(__name__)
logger.info("Bot initializing...")

# Initialize database
db = ConversationDB()

async def handle_message(update: Update, context):
    """Handle both text messages and voice notes"""
    user_id = update.effective_user.id
    processing_msg = None

    try:
        # Get user input (either text or voice)
        if update.message.text and not update.message.text.startswith('/'):
            logger.info(f"Text message received from user {user_id}")
            user_input = update.message.text
            processing_msg = await update.message.reply_text("Processing your message...")
            
        elif update.message.voice:
            # Handle voice note
            logger.info(f"Voice note received from user {user_id}")
            processing_msg = await update.message.reply_text("Processing voice note...")
            
            # Process with Whisper
            voice_note = await update.message.voice.get_file()
            user_input = await process_voice_note(voice_note)
            logger.info(f"Transcription completed - {len(user_input)} characters")
            
            # Show transcription
            await update.message.reply_text(f"Transcription:\n{user_input}")
        else:
            return

        # Store user message
        await db.add_message(user_id, "user", user_input)
        
        # Get system prompt and conversation history separately
        system_prompt = await db.get_user_prompt(user_id)
        conversation_history = await db.get_conversation_history(user_id)
        
        # Update processing message only if it's different
        if processing_msg and processing_msg.text != "Thinking...":
            try:
                await processing_msg.edit_text("Thinking...")
            except Exception as e:
                logger.debug(f"Could not update processing message: {e}")
            
        # Get Claude's response with history and system prompt
        response = await get_claude_response(conversation_history, system_prompt)
        
        # Store Claude's response
        await db.add_message(user_id, "assistant", response)
        
        # Send response to user
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await update.message.reply_text(f"Sorry, there was an error processing your message: {str(e)}")
    finally:
        # Clean up processing message
        if processing_msg:
            try:
                await processing_msg.delete()
            except Exception as e:
                logger.debug(f"Could not delete processing message: {e}")

async def start(update: Update, context):
    logger.info("Start handler called")
    user_id = update.effective_user.id
    
    try:
        await update.message.reply_text(
            "Hello! I'm your AI assistant. You can:\n"
            "• Send me text messages\n"
            "• Send me voice notes\n"
            "I'll remember our conversation and respond accordingly!"
        )
        logger.info("Start message sent successfully")
    except Exception as e:
        logger.error(f"Error in start handler: {e}", exc_info=True)

async def clear(update: Update, context):
    """Clear conversation history for user"""
    user_id = update.effective_user.id
    logger.info(f"Clearing conversation history for user {user_id}")
    
    try:
        await db.clear_user_history(user_id)
        await update.message.reply_text("Conversation history cleared!")
    except Exception as e:
        logger.error(f"Error clearing history: {e}")
        await update.message.reply_text("Sorry, there was an error clearing your conversation history.")

async def test(update: Update, context):
    logger.info(f"Test command received from user {update.effective_user.id}")
    await update.message.reply_text("Bot is working!")

async def set_prompt(update: Update, context):
    """Set the system prompt for the conversation"""
    user_id = update.effective_user.id
    
    # Check if there's a prompt in the message
    if not context.args:
        await update.message.reply_text(
            "Please provide a prompt after the command. For example:\n"
            "/setprompt You are a helpful AI assistant who speaks in a friendly tone."
        )
        return
    
    try:
        # Join all arguments into a single prompt string
        prompt = " ".join(context.args)
        
        # Save the prompt
        await db.set_user_prompt(user_id, prompt)
        
        await update.message.reply_text(
            "✅ System prompt set successfully!\n\n"
            f"Current prompt:\n{prompt}"
        )
        logger.info(f"Set new system prompt for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error setting prompt: {e}")
        await update.message.reply_text("Sorry, there was an error setting your prompt.")

async def show_prompt(update: Update, context):
    """Show the current system prompt"""
    user_id = update.effective_user.id
    
    try:
        prompt = await db.get_user_prompt(user_id)
        if prompt:
            await update.message.reply_text(
                "Current system prompt:\n\n"
                f"{prompt}"
            )
        else:
            await update.message.reply_text(
                "No system prompt set. Use /setprompt to set one.\n"
                "Example: /setprompt You are a helpful AI assistant."
            )
    except Exception as e:
        logger.error(f"Error showing prompt: {e}")
        await update.message.reply_text("Sorry, there was an error retrieving your prompt.")

def main():
    logger.info("Starting bot...")
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        logger.info("Registering command handlers...")
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("clear", clear))
        app.add_handler(CommandHandler("test", test))
        app.add_handler(CommandHandler("setprompt", set_prompt))
        app.add_handler(CommandHandler("showprompt", show_prompt))
        
        # Handle both text messages and voice notes
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND | filters.VOICE,
            handle_message
        ))
        
        # Add a catch-all handler to see all incoming updates
        async def log_update(update: Update, context):
            logger.info(f"Received update type: {update.message and update.message.text}")
            if update.message and update.message.text and update.message.text.startswith('/'):
                logger.info(f"Command received: {update.message.text}")
            logger.info(f"Full update: {update.to_dict()}")
        
        app.add_handler(MessageHandler(filters.ALL, log_update), group=1)
        
        logger.info("Starting polling...")
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()  # Clean up database connections

if __name__ == "__main__":
    main() 
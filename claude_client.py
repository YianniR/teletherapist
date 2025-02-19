from anthropic import AsyncAnthropic
from config import CLAUDE_API_KEY
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Create async client
anthropic = AsyncAnthropic(api_key=CLAUDE_API_KEY)

async def get_claude_response(conversation_history: List[Dict], system_prompt: str = None) -> str:
    """
    Get response from Claude API using conversation history and optional system prompt
    """
    try:
        logger.info("Sending request to Claude with conversation history")
        
        # Create message with optional system parameter
        kwargs = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1024,
            "messages": conversation_history
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
            logger.info("Including system prompt in request")
            
        message = await anthropic.messages.create(**kwargs)
        
        logger.info("Received response from Claude")
        return message.content[0].text
    except Exception as e:
        logger.error(f"Error in Claude API call: {e}")
        raise Exception(f"Error getting Claude response: {e}") 
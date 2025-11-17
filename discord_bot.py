import os
import logging
import discord
from discord.ext import commands
from ollama import AsyncClient, ResponseError
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('discord_bot')

# Environment Variables
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "MTM1MDgwMjc0MzYxODY5OTMwNA.Gdo19O.nkUdnBVvJ6WfsM7GaUOf3GxbJlkeSdsUYfqZ-k")
OLLAMA_HOST_URL = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434")

# Model Configuration (Defined in .env as well)
# Use 'mania' as the default main model as per your build steps
DEFAULT_MODEL_NAME = os.getenv("DEFAULT_MODEL_NAME", "mania")
# Use a common fallback model if needed (e.g., for a 'free' mode)
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "llama3") 

# Check for required configuration
if not DISCORD_TOKEN:
    log.error("DISCORD_BOT_TOKEN not found in environment variables. Exiting.")
    exit()

# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True # Required for reading message content in prefix commands
bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize Ollama Client
# Note: The Ollama client is initialized globally and set to async mode.
try:
    ollama_client = AsyncClient(host=OLLAMA_HOST_URL)
    log.info(f"Ollama client initialized, connecting to: {OLLAMA_HOST_URL}")
except Exception as e:
    log.error(f"Failed to initialize Ollama client: {e}")
    # Continue running the Discord bot, but generation commands will fail.

# --- Ollama API Functions ---

async def generate_stream(prompt: str, is_free_mode: bool):
    """
    An asynchronous generator that yields chunks of the LLM response.

    Args:
        prompt (str): The user's query.
        is_free_mode (bool): If True, use the FALLBACK_MODEL_NAME.

    Yields:
        str: Chunks of the generated response.
    """
    model_name = FALLBACK_MODEL_NAME if is_free_mode else DEFAULT_MODEL_NAME
    log.info(f"Generating response for model: {model_name}...")

    try:
        # The Ollama Python client supports asynchronous streaming
        stream = await ollama_client.generate(
            model=model_name,
            prompt=prompt,
            stream=True
        )
        
        # Stream the content chunks
        async for chunk in stream:
            if 'response' in chunk:
                yield chunk['response']
            
    except ResponseError as e:
        log.error(f"Ollama API Error ({model_name}): {e}")
        yield f"⚠️ Ollama API Error: Could not generate response. ({e})"
    except Exception as e:
        log.error(f"General generation error: {e}")
        yield f"❌ An unexpected error occurred during generation: {e}"


async def discord_generate(interaction_or_ctx, prompt_message: discord.Message | None, prompt_str: str | None, is_free_mode: bool):
    """
    Handles the full Discord interaction flow for generation.

    This function handles both ContextMenu (interaction) and Prefix (Context) commands.
    """
    
    # 1. Determine the source and initial message
    if isinstance(interaction_or_ctx, discord.Interaction):
        # Context Menu Command
        await interaction_or_ctx.response.defer() # Acknowledge the interaction
        source = interaction_or_ctx.followup
        # If the user used the context menu on a message, that message is the prompt
        prompt_text = prompt_message.content if prompt_message else "No message content found."
        
    else:
        # Prefix Command Context (ctx)
        source = interaction_or_ctx
        prompt_text = prompt_str
    
    if not prompt_text or prompt_text == "":
        await source.send("Prompt cannot be empty. Please provide text to analyze.")
        return

    # 2. Start generation and initial response
    # Use 'await source.send' for both interaction.followup and ctx.send
    initial_message = await source.send(f"🤖 **Generating ({'Free Mode' if is_free_mode else 'Mania Model'})...**")
    
    full_response = ""
    last_sent_content = ""
    chunk_count = 0
    
    # 3. Stream content
    async for chunk in generate_stream(prompt_text, is_free_mode):
        full_response += chunk
        chunk_count += 1
        
        # Edit the message every N chunks (or every 500 characters) to avoid rate limits
        # and minimize API calls while maintaining a streaming feel.
        if len(full_response) - len(last_sent_content) > 500 or chunk_count % 10 == 0:
             # Ensure the edited content is not empty
            if full_response.strip():
                try:
                    await initial_message.edit(content=full_response)
                    last_sent_content = full_response
                except discord.HTTPException as e:
                    # Ignore silent errors like "Message content is the same"
                    if "Message content is the same" not in str(e):
                        log.warning(f"Failed to edit message: {e}")
        
        # If full_response is too long, stop editing and send the rest
        if len(full_response) > 1900: # Discord limit is 2000 chars
            await initial_message.edit(content=full_response[:1900] + "\n\n... (Truncated)")
            break

    # 4. Final update
    if full_response.strip() and full_response != last_sent_content:
        await initial_message.edit(content=full_response)

    log.info(f"Generation complete for prompt: '{prompt_text[:50]}...'")


# --- Discord Commands ---

@bot.event
async def on_ready():
    """Bot initialization event."""
    log.info(f'{bot.user} has connected to Discord!')
    
    # Sync slash commands and context menus
    try:
        synced = await bot.tree.sync()
        log.info(f"Synced {len(synced)} command(s).")
    except Exception as e:
        log.error(f"Failed to sync commands: {e}")

# ====== Context Menu: 'mania' Model Generation ======
# This command appears in the right-click menu of a user message.
@bot.tree.context_menu(name="Generate with Mania")
async def mania_app(interaction: discord.Interaction, message: discord.Message):
    """Generates a response using the Mania model based on the selected message content."""
    # The 'message' object is the selected message, containing the prompt
    await discord_generate(interaction, message, None, False) # False = use DEFAULT_MODEL_NAME ('mania')

# ====== !mania Prefix Command: 'mania' Model Generation ======
@bot.command(name="mania", help="Generate a response using the Mania model.")
async def mania_prefix(ctx: commands.Context, *, prompt: str):
    """Generates a response using the Mania model."""
    # ctx is the command context, prompt is the remaining string
    await discord_generate(ctx, None, prompt, False) # False = use DEFAULT_MODEL_NAME ('mania')


# ====== !free Prefix Command: Fallback Model Generation (Example) ======
@bot.command(name="free", help="Generate a response using the Fallback model (llama3).")
async def free_prefix(ctx: commands.Context, *, prompt: str):
    """Generates a response using the Fallback model (e.g., llama3)."""
    # ctx is the command context, prompt is the remaining string
    await discord_generate(ctx, None, prompt, True) # True = use FALLBACK_MODEL_NAME ('llama3')

# ====== bot 実行 ======
if __name__ == "__main__":
    try:
        log.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Bot manually stopped.")
    except Exception:
        log.exception("Bot failed to start")

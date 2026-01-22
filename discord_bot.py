# ==========================================================
#  Discord Bot (GGUF / llama.cpp 高速版)
# ==========================================================
import os
import re
import json
import asyncio
import logging
import discord
from discord.ext import commands
from discord import app_commands
import subprocess
import sys
    
# ====== 設定 ======
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ====== ログ設定 ======
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
    force=True
)
log = logging.getLogger("LLM-Bot")

# ====== 検索データ読み込み ======
def load_search_results(file_path):
    search_list = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                search_list.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return search_list

SEARCH_RESULTS = load_search_results("dataset.jsonl")

# ====== ストリーミング生成 ======
async def generate_stream(prompt: str, match_cat):
    return "只今停止中です。"

# ====== Discord Bot ======
class ManiaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guild_messages = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        try:
            synced = await self.tree.sync()
            log.info(f"Commands synced globally ({len(synced)} commands).")
        except Exception:
            log.exception("Command sync failed")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info("Slash commands `/mania` and `/free` ready.")

bot = ManiaBot()

async def discord_generate(interaction: discord.Interaction, prompt: str, reply_to: str, is_base: bool = True):
    await interaction.response.send_message("生成中です…")
    msg = await interaction.original_response()

    collected = ""
    async for chunk in generate_stream(prompt, is_base):
        collected += chunk
        await msg.edit(
            content=(collected[:MAX_DISCORD_LENGTH] + "…")
            if len(collected) > MAX_DISCORD_LENGTH else collected
        )

    if reply_to:
        channel = interaction.channel
        try:
            target = await channel.fetch_message(int(reply_to))
            await target.reply(collected)
        except:
            await msg.edit(content=collected + "\n⚠️返信対象メッセージが見つかりませんでした。")
    else:
        await msg.edit(content=collected)
 
# ====== /mania ======
@bot.tree.command(name="mania", description="ウェブマニアとして回答します。")
@app_commands.describe(prompt="質問内容を入力してください。", reply_to="返信したいメッセージID")
async def mania_slash(interaction: discord.Interaction, prompt: str, reply_to: str = None):
    text = f"""system:これはスタンプです「:arigato: :boost: :ganbare: :gohan: :idai: :igyou: :iine: :imakita: :kaibun: :kami: :kaso: :kusa: :kyawa: :love: :maji: :mania: :nazo: :oj: :otukare: :owata: :oyasumi: :paooon: :saikou: :sorena: :tadaima: :tasikani: :tensai: :tya: :wakame: :wakaru: :wakayama: :wara: :webpaon: :yasume:」以下の文脈の内容を理解して適切に答えて下さい。
user:{prompt}
ウェブマニア:"""
    await discord_generate(interaction, text, reply_to, True)

# ====== /free ======
@bot.tree.command(name="free", description="自由に質問できます。")
@app_commands.describe(prompt="質問内容を入力してください。")
async def free_slash(interaction: discord.Interaction, prompt: str):
    await discord_generate(interaction, prompt, None, False)

# ====== /search コマンド ======
@bot.tree.command(name="search", description="キーワードに基づいて検索結果を返します。")
@app_commands.describe(keyword="検索したいキーワードを入力してください。")
async def search_slash(interaction: discord.Interaction, keyword: str):
    await interaction.response.send_message("検索中… ⏳")
    msg = await interaction.original_response()

    keyword_lower = keyword.lower()
    results = []

    for entry in SEARCH_RESULTS:
        instr = str(entry.get("instruction", "")).lower()
        out = str(entry.get("output", "")).lower()
        if keyword_lower in instr or keyword_lower in out:
            results.append(entry)

    if not results:
        await msg.edit(content=f"⚠️ キーワード `{keyword}` に一致する結果は見つかりませんでした。")
        return

    text = ""
    for r in results:
        text += f"{r.get('instruction','')}\n> {r.get('output','')}\n\n"
        if len(text) > 1800:
            text = text[:1800] + "…"
            break

    await msg.edit(content=text)

@bot.tree.command(name="settings", description="LLM の生成パラメータを変更します。")
@app_commands.describe(param="パラメータ名", value="値")
async def settings_slash(interaction: discord.Interaction, param: str, value: str = None):
    param = param.lower()

    if param == "show":
        text = "**現在の生成パラメータ:**\n"
        for k, v in GEN_CONFIG.items():
            text += f"- {k}: {v}\n"
        await interaction.response.send_message(text)
        return

    if param not in GEN_CONFIG:
        await interaction.response.send_message(f"⚠️ `{param}` は設定できません", ephemeral=True)
        return

    if value is None:
        await interaction.response.send_message(f"⚠️ `{param}` に新しい値を指定してください", ephemeral=True)
        return

    convert = NUMERIC_PARAMS.get(param, str)

    try:
        if param == "stop":
            v = [s.strip() for s in value.split(",")]
        else:
            v = convert(value)
    except Exception:
        await interaction.response.send_message(f"⚠️ `{param}` を `{convert.__name__}` に変換できません", ephemeral=True)
        return

    GEN_CONFIG[param] = v
    await interaction.response.send_message(f"🔧 `{param}` を `{v}` に変更しました。")

@bot.tree.command(name="name", description="AIくん？の名前を変える")
@app_commands.describe(name="名前を入れるのだ！")
async def setname(interaction: discord.Interaction, name: str):
    try:
        await interaction.client.user.edit(username=name)
        await interaction.response.send_message(f"名前を **{name}** に変更しました")
    except Exception as e:
        await interaction.response.send_message(f"変更エラー: {e}", ephemeral=True)

    await interaction.response.send_message("⚠️ 無効なパラメータです。")

@bot.tree.command(name="プロフィール", description="自身のプロフィールを設定できるよ！")
@app_commands.describe(text="入力してね")
async def setprofile(interaction: discord.Interaction, profile: str):
    try:
        await interaction.response.send_message(f"設定しました。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"エラーが起きました。")

#======= アプリコマンド =======
@bot.tree.context_menu(name="mania")
async def mania_app(interaction: discord.Interaction, prompt: discord.Message):
    await discord_generate(interaction, f"ユーザー:{prompt}\nウェブマニア:", None, True)

@bot.tree.context_menu(name="free")
async def mania_app(interaction: discord.Interaction, prompt: discord.Message):
    await discord_generate(interaction, prompt, None, False)

# ====== !mania プレフィックス ======
@bot.command(name="mania")
async def mania_prefix(ctx, *, prompt: str):
    await ctx.send("生成中です…")
    async for chunk in generate_stream(prompt, False):
        await ctx.send(chunk)

# ====== bot 実行 ======
if __name__ == "__main__":
    try:
        log.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Bot manually stopped.")
    except Exception:
        log.exception("Bot failed to start")

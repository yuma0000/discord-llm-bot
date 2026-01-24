# ==========================================================
#  Discord Bot (GGUF / llama.cpp 高速版)
# ==========================================================

import os
import re
import json
import asyncio
import logging
import requests
import discord

import random
import colorsys
from pathlib import Path
import textwrap
import math

from discord.ext import commands
from discord import app_commands
import firebase_admin
from firebase_admin import credentials, firestore

# ====== 設定 ======
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
MAX_NEW_TOKENS = 100
STREAM_DELAY = 0.3
MAX_DISCORD_LENGTH = 1800

# ====== 生成パラメータ設定 ======
GEN_CONFIG = {
    "max_tokens": 256,
    "temperature": 1.0,
    "top_p": 0.70,
    "top_k": 40,
    "repeat_penalty": 1.05,
    "stop": ["</s>"],
}

RUNTIME_CONFIG = {
    "n_threads": 8,
    "n_gpu_layers": 0,
    "n_ctx": 4096
}

NUMERIC_PARAMS = {
    "max_tokens": int,
    "temperature": float,
    "top_p": float,
    "top_k": int,
    "repeat_penalty": float,
    "stop": list,
}

# ====== firebase 設定 ======
# Railwayの環境変数に JSON丸ごと入れておく
cred_json = json.loads(os.environ["FIREBASE_CREDENTIALS"])

cred = credentials.Certificate(cred_json)
firebase_admin.initialize_app(cred)

db = firestore.client()

print("🔥 Firebase 初期化完了")

def save_profile(user_id: str, intro: str):
    doc_ref = db.collection("profiles").document(user_id)
    doc_ref.set(
        {
            "intro": intro,
        },
        merge=True
    )

def load_profile(user_id: str):
    doc_ref = db.collection("profiles").document(user_id)
    doc = doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    return data.get("intro")

# ====== minecraft ======
mc_api = "https://api.mcsrvstat.us/3/webm-mc.chasyumen.net"

# ====== 0.0035 ======
game_api = "https://store.steampowered.com/api/appdetails?appids=4234500&cc=jp&l=ja"

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

#SEARCH_RESULTS = load_search_results("dataset.jsonl")
SEARCH_RESULTS = ""

# ====== miq 生成 ======
signature = "まにまにあ"
W, H = 800, 500
TOP_MARGIN = 80
BOTTOM_MARGIN = 80
AVAILABLE_HEIGHT = H - TOP_MARGIN - BOTTOM_MARGIN
BASE_FONT_SIZE = 24
LINE_HEIGHT_RATE = 1.4
MAX_LINES = math.floor(AVAILABLE_HEIGHT / (BASE_FONT_SIZE * LINE_HEIGHT_RATE))

s = 0.50
v = 0.80

def wrap_by_lines(text, max_lines):
    for chars in range(30, 6, -1):
        lines = textwrap.wrap(text, chars)
        if len(lines) <= max_lines:
            return lines
    return textwrap.wrap(text, 6)

# ====== ストリーミング生成 ======
async def generate_stream(prompt: str, match_cat):
    text = "## 現在利用不可です。"

    yield text
    await asyncio.sleep(STREAM_DELAY)

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

    await discord_generate(interaction, prompt, reply_to, True)

# ====== /free ======
@bot.tree.command(name="free", description="自由に質問できます。")
@app_commands.describe(prompt="質問内容を入力してください。")
async def free_slash(interaction: discord.Interaction, prompt: str):
    await discord_generate(interaction, prompt, None, False)

# ====== /search コマンド ======
#@bot.tree.command(name="search", description="キーワードに基づいて検索結果を返します。")
#@app_commands.describe(keyword="検索したいキーワードを入力してください。")
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

@bot.tree.command(name="自己紹介", description="自己紹介を保存または表示をします")
@app_commands.describe(text="自己紹介を入力してね、何も無ければ表示をします。")
async def self_intro(interaction: discord.Interaction, text: str = None):
    user_id = str(interaction.user.id)

    if text and text.strip():
        save_profile(user_id, text.strip())
        await interaction.response.send_message("自己紹介を保存したよ")
        return

    else:
        intro = load_profile(user_id)
        if intro:
            await interaction.response.send_message(intro)
        else:
            await interaction.response.send_message("まだ自己紹介は保存されてないよ")

@bot.tree.command(name="マニア鯖のステータス", description="エビ🦐ちゃーしゅ運営のマイクラ鯖のステータスと表示出来ます")
async def mcserver(interaction: discord.Interaction):
    try:
        res = requests.get(mc_api)
        res.raise_for_status()
        data = res.json()
        if data.get("online"):
            text = f"""
                # サバ名: {data.get("motd").get("clean")}
                ## 人数: {data.get("players").get("online")}
                ### バージョン: {data.get("version")}
            """
        else:
            text = "鯖は現在オフラインです。"
    except Exception as e:
        print(e)
        text = "情報が習得出来ませんでした。"

    await interaction.response.send_message(text)

@bot.tree.command(name="マニアプロダクション", description="MANIA PRODUCTIONの0.0035%のsteamを表示します")
async def maniaproduction(interaction: discord.Interaction):
    try:
        res = requests.get(game_api)
        res.raise_for_status()
        data = res.json()
        if data.get("4234500").get("success"):
            text = f"""
                # ゲーム名: {data.get("4234500").get("data").get("name")}
                ## デベロッパー: {data.get("4234500").get("data").get("developers")[0]}
                ### リリース日: {data.get("4234500").get("data").get("release_date").get("date")}
            """
        else:
            text = "ゲームが見つかりませんでした。"
    except Exception as e:
        print(e)
        text = "情報が習得出来ませんでした。"

    await interaction.response.send_message(text)

@bot.tree.command(name="name", description="AIくん？の名前を変える")
@app_commands.describe(name="名前を入れるのだ！")
async def setname(interaction: discord.Interaction, name: str):
    try:
        await interaction.client.user.edit(username=name)
        await interaction.response.send_message(f"名前を **{name}** に変更しました")
    except Exception as e:
        await interaction.response.send_message(f"変更エラー: {e}", ephemeral=True)

    await interaction.response.send_message("⚠️ 無効なパラメータです。")

#======= アプリコマンド =======
@bot.tree.context_menu(name="mania")
async def mania_app(interaction: discord.Interaction, prompt: discord.Message):
    messages = [
        {"role": "system", "content": "あなたはウェブマニアです。以下の内容に適切に返答を返して下さい！"},
        {"role": "user", "content": prompt.content}
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    await discord_generate(interaction, text, None, True)

@bot.tree.context_menu(name="free")
async def free_app(interaction: discord.Interaction, prompt: discord.Message):
    await discord_generate(interaction, str(prompt.content), None, False)

@bot.tree.context_menu(name="Make is a quate", description="MiQを作成します")
async def miq(interaction: discord.Interaction, text: discord.Message):
    try:
        lines = wrap_by_lines(text, MAX_LINES)
        font_size = mln(
            BASE_FONT_SIZE,
            int(AVAILABLE_HEIGHT / (len(lines) * LINE_HEIGHT_RATE))
        )
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        bg_color = f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"
        tspans = []
        start_dy = -(len(lines) - 1) / 2 * font_size * LINE_HEIGHT_RATE
        for i, line in enumerate(line):
            dy = start_dy if i == 0 else font_size * LINE_HEIGHT_RATE
            tspans.append(
                f'<tspan x="50%" dy="{dy}">{line}</tspan>'
            )
        tspan_text = "\n".join(tspans)

        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
            <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">

            <rect width="100%" height="100%" fill="{bg_color}"/>

            <text x="50%" y="50%"
                text-anchor="middle"
                dominant-baseline="middle"
                font-size="{font_size}"
                font-family="sans-serif"
                fill="#121212">
                {tspan_text}
            </text>

            <text x="{W-16}" y="{H-16}"
                text-anchor="end"
                font-size="14"
                fill="#333"
                font-family="sans-serif">
                {signature}
            </text>

        </svg>
        '''

        Path("quote.svg").write_text(svg, encoding="utf-8")
        await interaction.response.send(file=discord.file("quote.svg"))

    except Exception as e:
        print(e)
        text = "MiQが作成出来ませんでした。"
        await interaction.response.send_message(text)

# ====== !mania プレフィックス ======
@bot.command(name="mania")
async def mania_prefix(ctx, *, prompt: str):
    await ctx.send("生成中です…")
    async for chunk in generate_stream(prompt, False):
        await ctx.send(chunk)

@bot.event
async def on_ready():
    print("Bot logged in as", bot.user)

# ====== bot 実行 ======
if __name__ == "__main__":
    try:
        log.info("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Bot manually stopped.")
    except Exception:
        log.exception("Bot failed to start")

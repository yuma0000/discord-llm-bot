# ==========================================================
#  Discord Bot (GGUF / llama.cpp 高速版)
# ==========================================================

import os
import re
import json
import base64
import asyncio
import logging
import requests
import discord

import random
import colorsys
from pathlib import Path
import textwrap
import math
import subprocess
from datetime import datetime

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
mc_api = "https://api.mcsrvstat.us/3/mc.webmfan.net"

# ====== 0.0035 ======
game_api = "https://store.steampowered.com/api/appdetails?appids=4234500&cc=jp&l=ja"
play_api = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid=4234500"

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
W, H = 500, 300
CX, CY = W // 2, H // 2
HEART = "♥️"
TOP_MARGIN = 80
BOTTOM_MARGIN = 80
AVAILABLE_HEIGHT = H - TOP_MARGIN - BOTTOM_MARGIN
BASE_FONT_SIZE = 24
LINE_HEIGHT_RATE = 1.4
MAX_LINES = math.floor(AVAILABLE_HEIGHT / (BASE_FONT_SIZE * LINE_HEIGHT_RATE))

s = 0.50
v = 0.80

emoji_pattern = re.compile(r"<:\w+:(\d+)>")

async def wrap_by_lines(text: str):
    texts = []
    lines = text.split("\n")
    for line in lines:
        if emoji_pattern.search(line):
            texts.append(line)
        else:
            texts.extend(textwrap.wrap(line, 10))
    return texts

async def emoji_convert(text: str):
    result = []
    last = 0

    for m in emoji_pattern.finditer(text):
        start, end = m.span()
        emoji_id = m.group(1)

        if start > last:
            result.append(text[last:start])

        result.append(emoji_id)
        last = end
        
    if last < len(text):
        result.append(text[last:])

    return result

async def make_hearts():
    hearts = []
    step = 20
    old_scale = 0
    positined = []
    for i in range(0, W, step):
        positined.append((i, 0))
    for i in range(0, H, step):
        positined.append((W, i))
    for i in range(W, 0, -step):
        positined.append((i, H))
    for i in range(H, 0, -step):
        positined.append((0, i))

    for x, y in positined:
        dx = x - CX
        dy = y - CY

        scale = random.uniform(0.4, 1.0)
        cs = scale - old_scale
        if cs < 0.1 and cs > -0.1:
            continue

        old_scale = scale
        ax, ay = dx * scale, dy * scale

        size = 48
        rotate = 0
        color = ["#ff4d6d", "#ff758f", "#ff8fab"][i % 3]

        hearts.append(
            f'''
            <text x="{ax + CX}" y="{ay + CY}"
                font-size="{size * scale}"
                text-anchor="middle"
                dominant-baseline="middle"
                    transform="rotate({rotate},{x},{y})"
                    fill="{color}">
                    {HEART}
            </text>
            '''
        )
    return "\n".join(hearts)

async def build_text_groups(lines, font_size):
    if not lines:
        return ""

    svg_groups = []

    y = CY - (len(lines) - 1) * font_size * LINE_HEIGHT_RATE / 2

    for line in lines:
        tokens = await emoji_convert(line)

        width = 0
        for t in tokens:
            if t.isdigit():
                width += font_size
            else:
                width += len(t) * font_size * 0.6

        x = CX - width / 2
        elements = []

        for t in tokens:
            if t.isdigit():
                try:
                    img = requests.get(
                        f"https://cdn.discordapp.com/emojis/{t}.png?size=96",
                        timeout=5
                    ).content
                    b64 = base64.b64encode(img).decode()

                    elements.append(
                        f'''
                        <image
                          href="data:image/png;base64,{b64}"
                          x="{x}"
                          y="{y - font_size * 0.8}"
                          width="{font_size}"
                          height="{font_size}" />
                        '''
                    )
                except Exception as e:
                    log.exception(e)

                x += font_size

            else:
                elements.append(
                    f'''
                    <text
                      x="{x}"
                      y="{y}"
                      font-size="{font_size}"
                      dominant-baseline="middle"
                      text-anchor="start">
                      {t}
                    </text>
                    '''
                )
                x += len(t) * font_size * 0.6

        svg_groups.append(
            f'<g>{"".join(elements)}</g>'
        )

        y += font_size * LINE_HEIGHT_RATE

    return "".join(svg_groups)
        
async def remove_file(file: str):
    if os.path.exists(file):
        os.remove(file)
        
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

async def discord_collections(interaction: discord.Interaction, message: str, document: str, not_mess: str, add_mess: str, del_mess: str):
    try:
        doc_ref = db.collection("discord_collections").document(document)
        doc = doc_ref.get()

        if not doc.exists:
            return None
        else:
            data = doc.to_dict()
        
        if not message:
            if not data:
                text = not_mess
            else:
                text = random.choice(list(data.values()))
        else:
            key = None
            for k, v in data.items():
                if v == message:
                    key = k
                    break
            
            if key:
                doc_ref.update({
                    key: firestore.DELETE_FIELD
                })
                text = del_mess
            else:
                key = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                doc_ref.set({
                    key: message
                }, merge=True)
                text = add_mess

    except Exception as e:
        log.exception(e)
        text = "エラーが発生いたしました。"

    await interaction.response.send_message(text)

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

#====== /settings ======
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
            embed = discord.Embed(
                title=f'サバ名: {data.get("motd").get("clean")[0]}',
                color=discord.Color.grey()
            )

            embed.add_field(name="人数", value=data.get("players").get("online"), inline=False)
            embed.add_field(name="バージョン", value=data.get("version"), inline=False)
            await interaction.response.send_message(embed=embed)
            return True
        else:
            text = "鯖は現在オフラインです。"
    except Exception as e:
        log.exception(e)
        text = "情報が取得出来ませんでした。"

    await interaction.response.send_message(text)

@bot.tree.command(name="マニアプロダクション", description="MANIA PRODUCTIONの0.0035%のsteamを表示します")
@app_commands.describe(add="テキストを追加できます")
async def maniaproduction(interaction: discord.Interaction, add :str = None):
    try:
        game_res = requests.get(game_api)
        game_res.raise_for_status()
        game_data = game_res.json()

        play_res = requests.get(play_api)
        play_res.raise_for_status()
        play_data = play_res.json()
        
        if game_data.get("4234500").get("success"):
            embed = discord.Embed(
                title=f'ゲーム名: {game_data.get("4234500").get("data").get("name")}',
                color=discord.Color.grey()
            )

            embed.add_field(name="現在のプレイヤー数", value=play_data.get("response").get("player_count"), inline=False)
            embed.add_field(name="デベロッパー", value=game_data.get("4234500").get("data").get("developers")[0], inline=False)
            embed.add_field(name="リリース日", value=game_data.get("4234500").get("data").get("release_date").get("date"), inline=False)
            embed.add_field(name="追記", value=add, inline=False)
            await interaction.response.send_message(embed=embed)
            return True
        else:
            text = "ゲームが見つかりませんでした。"
    except Exception as e:
        log.exception(e)
        text = "情報が取得出来ませんでした。"

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

#====== /nitro_present ======
@bot.tree.command(name="nitro_present", description="ニトロをプレゼント致します。")
@app_commands.describe(url="追加または削除をします")
async def nitro_present(interaction: discord.Interaction, url: str = None):
    await discord_collections(interaction, url, "nitro_present", "残念ながら現在nitroの配布は行っておりません。", "リンクを追加致しました。", "リンクを削除致しました。")

#====== /random_message
@bot.tree.command(name="random_message", description="ランダムに追加したメッセージを返します")
@app_commands.describe(message="追加または削除をします")
async def random_message(interaction: discord.Interaction, message: str = None):
    await discord_collections(interaction, message, "random_message", "メッセージが一つも登録されてません。", "メッセージを追加しました。", "メッセージを削除致しました。")

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

@bot.tree.context_menu(name="Make_is_a_Quate")
async def miq(interaction: discord.Interaction, text: discord.Message):
    try:
        lines = await wrap_by_lines(text.content)
        font_size = min(BASE_FONT_SIZE, int(AVAILABLE_HEIGHT / (len(lines) * LINE_HEIGHT_RATE)))

        svg = f'''<?xml version="1.0" encoding="UTF-8"?>
        <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}"
            xmlns="http://www.w3.org/2000/svg">

            <rect width="100%" height="100%" fill="#fff0f3"/>
            {await make_hearts()}
            {await build_text_groups(lines, font_size)}

            <text x="{W-16}" y="{H-16}"
                text-anchor="end"
                font-size="14"
                fill="#777">
                {signature}
            </text>
        </svg>
        '''
        
        """
        lines = wrap_by_lines(text.content)
        font_size = min(
            BASE_FONT_SIZE,
            int(AVAILABLE_HEIGHT / (len(lines) * LINE_HEIGHT_RATE))
        )
        h = random.random()
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        bg_color = f"rgb({int(r*255)}, {int(g*255)}, {int(b*255)})"
        tspans = []
        start_dy = -(len(lines) - 1) / 2 * font_size * LINE_HEIGHT_RATE
        for i, line in enumerate(lines):
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
                fill="#777"
                font-family="sans-serif">
                {signature}
            </text>

        </svg>
        '''
        """

        h = random.random()
        with open(str(h) + ".svg", "w", encoding="utf-8") as f:
            f.write(svg)

        subprocess.run(
            ["inkscape", str(h) + ".svg", "--export-type=png", "--export-filename=" + str(h) + ".png"],
            check=True
        )

        await interaction.response.defer()
        await interaction.followup.send(file=discord.File(str(h) + ".png"))

        remove_file(str(h) + ".svg")
        remove_file(str(h) + ".png")
        
    except Exception as e:
        log.exception(e)
        text = "MiQが作成出来ませんでした。"
        await interaction.followup.send(content=text)

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

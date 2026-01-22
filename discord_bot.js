/*****************************************************************
 * Discord Bot (discord.js v14)
 * - /mania /free /search
 * - /自己紹介 入力 / 出力
 * - MariaDB (ユーザー毎保存)
 *****************************************************************/

import 'dotenv/config';
import fs from "fs";
import mysql from "mysql2/promise";
import {
  Client,
  GatewayIntentBits,
  SlashCommandBuilder,
  REST,
  Routes,
} from "discord.js";

/* =========================
   設定
========================= */
const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.CLIENT_ID;
const MAX_DISCORD_LENGTH = 1900;

/* =========================
   MariaDB 接続
========================= */
const pool = mysql.createPool({
  host: process.env.DB_HOST,
  port: process.env.DB_PORT,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  database: process.env.DB_NAME,
  waitForConnections: true,
  connectionLimit: 10,
});

/* =========================
   DB 初期化
========================= */
await pool.execute(`
  CREATE TABLE IF NOT EXISTS profiles (
    user_id VARCHAR(32) PRIMARY KEY,
    profile TEXT NOT NULL,
    updated_at BIGINT NOT NULL
  ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
`);

/* =========================
   検索データ読み込み
========================= */
const SEARCH_RESULTS = fs.existsSync("dataset.jsonl")
  ? fs.readFileSync("dataset.jsonl", "utf-8")
      .split("\n")
      .filter(Boolean)
      .map(l => { try { return JSON.parse(l); } catch { return null; } })
      .filter(Boolean)
  : [];

/* =========================
   DB操作
========================= */
async function saveProfile(userId, text) {
  await pool.execute(
    `
    INSERT INTO profiles (user_id, profile, updated_at)
    VALUES (?, ?, ?)
    ON DUPLICATE KEY UPDATE
      profile = VALUES(profile),
      updated_at = VALUES(updated_at)
    `,
    [userId, text, Date.now()]
  );
}

async function getProfile(userId) {
  const [rows] = await pool.execute(
    `SELECT profile FROM profiles WHERE user_id = ?`,
    [userId]
  );
  return rows.length ? rows[0].profile : null;
}

/* =========================
   LLM ストリーミング（仮）
========================= */
async function* generateStream(prompt, isBase) {
  yield "只今停止中です。";
}

/* =========================
   Discord Client
========================= */
const client = new Client({
  intents: [GatewayIntentBits.Guilds],
});

/* =========================
   Slash Commands 定義
========================= */
const commands = [
  new SlashCommandBuilder()
    .setName("mania")
    .setDescription("ウェブマニアとして回答します")
    .addStringOption(o =>
      o.setName("prompt").setDescription("質問内容").setRequired(true))
    .addStringOption(o =>
      o.setName("reply_to").setDescription("返信先メッセージID")),

  new SlashCommandBuilder()
    .setName("free")
    .setDescription("自由に質問できます")
    .addStringOption(o =>
      o.setName("prompt").setDescription("質問内容").setRequired(true)),

  new SlashCommandBuilder()
    .setName("search")
    .setDescription("キーワード検索")
    .addStringOption(o =>
      o.setName("keyword").setDescription("検索語").setRequired(true)),

  new SlashCommandBuilder()
    .setName("自己紹介")
    .setDescription("自己紹介を登録・表示します")
    .addSubcommand(s =>
      s.setName("入力")
        .setDescription("自己紹介を登録")
        .addStringOption(o =>
          o.setName("内容")
            .setDescription("自己紹介文")
            .setRequired(true)))
    .addSubcommand(s =>
      s.setName("出力")
        .setDescription("自己紹介を表示")),
];

/* =========================
   Slash Commands 登録
========================= */
const rest = new REST({ version: "10" }).setToken(DISCORD_TOKEN);
await rest.put(
  Routes.applicationCommands(CLIENT_ID),
  { body: commands.map(c => c.toJSON()) }
);

/* =========================
   共通生成処理
========================= */
async function discordGenerate(interaction, prompt, replyTo, isBase) {
  await interaction.reply("生成中です…");
  let collected = "";

  for await (const chunk of generateStream(prompt, isBase)) {
    collected += chunk;
    await interaction.editReply(
      collected.length > MAX_DISCORD_LENGTH
        ? collected.slice(0, MAX_DISCORD_LENGTH) + "…"
        : collected
    );
  }

  if (replyTo) {
    try {
      const target = await interaction.channel.messages.fetch(replyTo);
      await target.reply(collected);
    } catch {
      await interaction.editReply(collected + "\n⚠️返信先が見つかりませんでした。");
    }
  } else {
    await interaction.editReply(collected);
  }
}

/* =========================
   Interaction Handler
========================= */
client.on("interactionCreate", async interaction => {
  if (!interaction.isChatInputCommand()) return;

  /* /mania */
  if (interaction.commandName === "mania") {
    const prompt = interaction.options.getString("prompt");
    const replyTo = interaction.options.getString("reply_to");

    const profile = await getProfile(interaction.user.id);

    const text = `
system:これはスタンプです
user_profile:${profile ?? "未登録"}
user:${prompt}
ウェブマニア:
`;
    return discordGenerate(interaction, text, replyTo, true);
  }

  /* /free */
  if (interaction.commandName === "free") {
    const prompt = interaction.options.getString("prompt");
    return discordGenerate(interaction, prompt, null, false);
  }

  /* /search */
  if (interaction.commandName === "search") {
    const keyword = interaction.options.getString("keyword").toLowerCase();
    await interaction.reply("検索中… ⏳");

    const hits = SEARCH_RESULTS
      .filter(r => JSON.stringify(r).toLowerCase().includes(keyword))
      .slice(0, 5);

    return interaction.editReply(
      hits.length
        ? hits.map(h => "• " + JSON.stringify(h)).join("\n")
        : "見つかりませんでした。"
    );
  }

  /* /自己紹介 */
  if (interaction.commandName === "自己紹介") {
    const sub = interaction.options.getSubcommand();
    const userId = interaction.user.id;

    if (sub === "入力") {
      const text = interaction.options.getString("内容");
      await saveProfile(userId, text);
      return interaction.reply("✅ 自己紹介を保存しました。");
    }

    if (sub === "出力") {
      const profile = await getProfile(userId);
      return interaction.reply(
        profile
          ? `🧾 **あなたの自己紹介**\n${profile}`
          : "⚠️ まだ自己紹介が登録されていません。"
      );
    }
  }
});

/* =========================
   起動
========================= */
client.once("ready", () => {
  console.log(`Logged in as ${client.user.tag}`);
});

client.login(DISCORD_TOKEN);

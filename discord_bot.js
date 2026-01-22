import 'dotenv/config';
import {
  Client,
  GatewayIntentBits,
  SlashCommandBuilder,
  REST,
  Routes,
} from "discord.js";
import fs from "fs";

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const CLIENT_ID = process.env.CLIENT_ID;

const MAX_DISCORD_LENGTH = 1900;

// ===== 検索データ読み込み =====
const SEARCH_RESULTS = fs
  .readFileSync("dataset.jsonl", "utf-8")
  .split("\n")
  .filter(Boolean)
  .map(line => {
    try { return JSON.parse(line); }
    catch { return null; }
  })
  .filter(Boolean);

// ===== ストリーミング生成（仮）=====
async function* generateStream(prompt, isBase) {
  yield "只今停止中です。";
}

// ===== Discord Client =====
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

client.once("ready", () => {
  console.log(`Logged in as ${client.user.tag}`);
});

// ===== Slash Commands =====
const commands = [
  new SlashCommandBuilder()
    .setName("mania")
    .setDescription("ウェブマニアとして回答します。")
    .addStringOption(o =>
      o.setName("prompt")
        .setDescription("質問内容")
        .setRequired(true))
    .addStringOption(o =>
      o.setName("reply_to")
        .setDescription("返信したいメッセージID")
        .setRequired(false)
    ),

  new SlashCommandBuilder()
    .setName("free")
    .setDescription("自由に質問できます。")
    .addStringOption(o =>
      o.setName("prompt")
        .setDescription("質問内容")
        .setRequired(true)
    ),

  new SlashCommandBuilder()
    .setName("search")
    .setDescription("キーワード検索")
    .addStringOption(o =>
      o.setName("keyword")
        .setDescription("検索ワード")
        .setRequired(true)
    ),
];

// ===== コマンド登録 =====
const rest = new REST({ version: "10" }).setToken(DISCORD_TOKEN);

(async () => {
  await rest.put(
    Routes.applicationCommands(CLIENT_ID),
    { body: commands.map(c => c.toJSON()) }
  );
  console.log("Slash commands synced");
})();

// ===== 生成共通処理 =====
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
      await interaction.editReply(
        collected + "\n⚠️返信対象メッセージが見つかりませんでした。"
      );
    }
  } else {
    await interaction.editReply(collected);
  }
}

// ===== Interaction Handler =====
client.on("interactionCreate", async interaction => {
  if (!interaction.isChatInputCommand()) return;

  if (interaction.commandName === "mania") {
    const prompt = interaction.options.getString("prompt");
    const replyTo = interaction.options.getString("reply_to");

    const text = `
system:これはスタンプです「:arigato: :boost: :mania:」
user:${prompt}
ウェブマニア:
`;
    await discordGenerate(interaction, text, replyTo, true);
  }

  if (interaction.commandName === "free") {
    const prompt = interaction.options.getString("prompt");
    await discordGenerate(interaction, prompt, null, false);
  }

  if (interaction.commandName === "search") {
    const keyword = interaction.options.getString("keyword").toLowerCase();
    await interaction.reply("検索中… ⏳");

    const hits = SEARCH_RESULTS.filter(r =>
      JSON.stringify(r).toLowerCase().includes(keyword)
    ).slice(0, 5);

    await interaction.editReply(
      hits.length
        ? hits.map(h => "• " + JSON.stringify(h)).join("\n")
        : "見つかりませんでした。"
    );
  }
});

client.login(DISCORD_TOKEN);

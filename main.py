import os
import re
import aiohttp
import discord
import chat_exporter
import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = discord.Client(intents=intents)

# --- CONFIGURATION ---
GUILD_ID = 1305137008481665096  # Remplacez par l'ID de votre serveur


async def telecharger_et_remplacer_medias(transcript_html, channel_id):
    """Détecte tous les liens de médias Discord dans l'HTML, les télécharge et remplace les liens."""
    # Expression régulière pour détecter les URLs de médias Discord (images, pièces jointes, avatars, émojis)
    pattern = r'https://(?:cdn|media)\.discordapp\.(?:com|net)/[^\s"\'<>]+'
    urls_trouvees = list(set(re.findall(pattern, transcript_html)))

    if not urls_trouvees:
        return transcript_html

    media_dir = os.path.join("public", "media", str(channel_id))
    os.makedirs(media_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for i, url_raw in enumerate(urls_trouvees):
            try:
                # Corriger les caractères HTML encodés comme &amp; dans les URLs
                url_download = url_raw.replace('&amp;', '&')
                
                # Extraire un nom de fichier propre
                url_sans_params = url_download.split('?')[0]
                nom_original = url_sans_params.split('/')[-1]
                if not nom_original or len(nom_original) > 40:
                    nom_original = f"fichier_{i}.bin"

                nom_fichier_local = f"{i}_{nom_original}"
                chemin_fichier_local = os.path.join(media_dir, nom_fichier_local)

                # Télécharger le média
                async with session.get(url_download) as response:
                    if response.status == 200:
                        contenu = await response.read()
                        with open(chemin_fichier_local, "wb") as f:
                            f.write(contenu)

                        # Remplacer le lien distant par le lien relatif vers le fichier local
                        lien_relatif = f"media/{channel_id}/{nom_fichier_local}"
                        transcript_html = transcript_html.replace(url_raw, lien_relatif)
            except Exception as e:
                print(f"Erreur téléchargement média ({url_raw}): {e}")

    return transcript_html


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    guild = bot.get_guild(GUILD_ID)

    if not guild:
        print(f"Erreur : Serveur {GUILD_ID} introuvable.")
        await bot.close()
        return

    os.makedirs("public", exist_ok=True)
    date_du_jour = datetime.date.today().strftime("%d/%m/%Y")
    categories_data = {}

    # 1. SALONS TEXTUELS
    print("--- Extraction des salons textuels et téléchargement des médias ---")
    for channel in guild.text_channels:
        if not channel.permissions_for(guild.me).read_message_history:
            continue

        cat_name = channel.category.name if channel.category else "GÉNÉRAL"
        if cat_name not in categories_data:
            categories_data[cat_name] = []

        try:
            print(f"Traitement : #{channel.name}...")
            transcript = await chat_exporter.export(
                channel,
                limit=None,
                tz_info="Europe/Paris",
                military_time=True,
                bot=bot
            )

            if transcript:
                # Localisation de tous les fichiers/images
                transcript_local = await telecharger_et_remplacer_medias(transcript, channel.id)
                
                filename = f"channel_{channel.id}.html"
                with open(os.path.join("public", filename), "w", encoding="utf-8") as f:
                    f.write(transcript_local)
                categories_data[cat_name].append((f"💬 #{channel.name}", filename))
        except Exception as e:
            print(f"Erreur sur le salon #{channel.name}: {e}")

    # 2. FORUMS
    print("--- Extraction des forums et téléchargement des médias ---")
    for forum in guild.forums:
        if not forum.permissions_for(guild.me).read_message_history:
            continue

        cat_name = forum.category.name if forum.category else "FORUMS"
        if cat_name not in categories_data:
            categories_data[cat_name] = []

        threads = list(forum.threads)
        try:
            async for archived_thread in forum.archived_threads(limit=None):
                threads.append(archived_thread)
        except Exception as e:
            print(f"Erreur archives forum {forum.name}: {e}")

        for thread in threads:
            try:
                print(f"Traitement : [{forum.name}] {thread.name}...")
                transcript = await chat_exporter.export(
                    thread,
                    limit=None,
                    tz_info="Europe/Paris",
                    military_time=True,
                    bot=bot
                )

                if transcript:
                    transcript_local = await telecharger_et_remplacer_medias(transcript, thread.id)
                    filename = f"thread_{thread.id}.html"
                    with open(os.path.join("public", filename), "w", encoding="utf-8") as f:
                        f.write(transcript_local)
                    categories_data[cat_name].append((f"📌 [{forum.name}] {thread.name}", filename))
            except Exception as e:
                print(f"Erreur sur le sujet {thread.name}: {e}")

    # 3. CRÉATION DU SOMMAIRE INDEX.HTML
    html_categories = ""
    for cat, salons in categories_data.items():
        if not salons:
            continue
        liens = "".join([f'<li><a href="{file}">{name}</a></li>' for name, file in salons])
        html_categories += f"""
        <div class="category">
            <h2>{cat.upper()}</h2>
            <ul>{liens}</ul>
        </div>
        """

    html_index = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Archives - {guild.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #1e1f22; color: #dbdee1; padding: 30px; margin: 0; }}
        .container {{ max-width: 800px; margin: 0 auto; background: #2b2d31; padding: 25px; border-radius: 8px; }}
        h1 {{ color: #ffffff; border-bottom: 2px solid #3f4147; padding-bottom: 10px; margin-top: 0; }}
        .category {{ margin-top: 25px; }}
        h2 {{ font-size: 14px; color: #949ba4; letter-spacing: 0.5px; margin-bottom: 10px; }}
        ul {{ list-style: none; padding: 0; margin: 0; }}
        li {{ margin-bottom: 8px; }}
        a {{ display: block; background: #313338; color: #949ba4; text-decoration: none; padding: 10px 14px; border-radius: 4px; font-weight: 500; transition: all 0.2s; }}
        a:hover {{ background: #35373c; color: #ffffff; padding-left: 18px; }}
        p.date {{ color: #949ba4; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Archives de {guild.name}</h1>
        <p class="date">Dernière mise à jour : {date_du_jour}</p>
        {html_categories}
    </div>
</body>
</html>"""

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(html_index)

    print("--- Exportation globale terminée : Fichiers et médias sauvegardés localement ---")
    await bot.close()

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)

import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from .utils import checks


from random import choice
import xml.etree.ElementTree as ET
import aiohttp
import os


class TooManyTagsError(Exception):
    pass


MAX_FILTERS = 10


class Lewd:
    """Commandes NSFW"""

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.settings = dataIO.load_json("data/lewd/settings.json")
        self.filter = dataIO.load_json("data/lewd/filter.json")

    def __unload(self):
        self.session.close()

    @commands.command(pass_context=True, no_pm=True)
    async def e621(self, ctx, *tags):
        """Rechercher sur e621!

        Si aucun tag n'est donné, donne une image aléatoire
        """
        search = ""
        user = ctx.message.author
        server = ctx.message.server
        channel = ctx.message.channel
        self.check_settings(ctx)
        if self.settings[server.id][channel.id] == "off":
            await self.bot.say("Le porno est désactivé dans ce canal.")
            return
        if self.settings[server.id][channel.id] == "sfw" and self.contains_nsfw(tags):
            await self.bot.say("Bien essayé")
            return
        msg = await self.bot.say("Chargement...")
        if tags:
            search = " ".join(tags)
        else:
            search = "random"
        try:
            constructed = self.construct_url("e621", ctx, tags)
            url = constructed[0]
            filters = constructed[1]
            headers = {'User-Agent': 'API Discord Bot'}
            async with self.session.get(url, headers=headers) as r:
                results = await r.json()
            results = [res for res in results if not any(
                x in res["tags"] for x in filters) and not res["file_url"].endswith((".mp4", ".swf", ".webm"))]
            random_post = choice(results)
            embed = self.e621_embed(random_post, search)
            await self.bot.edit_message(msg, new_content="{0.mention}:".format(user), embed=embed)
        except IndexError:
            await self.bot.edit_message(msg, "{0.mention}, Aucun résultat "
                                        "trouvé pour `{1}`".format(user, search))
        except TooManyTagsError:
            await self.bot.edit_message(msg, "Trop de tags")
        except Exception as e:
            await self.bot.edit_message(msg, "Une exception inconnue s'est produite: `{}`".format(e))

    @commands.command(pass_context=True, no_pm=True)
    async def rule34(self, ctx, *tags: str):
        """Rechercher sur rule34!

        Si aucun tag n'est donné, donne une image aléatoire
        """
        search = ""
        user = ctx.message.author
        server = ctx.message.server
        channel = ctx.message.channel
        self.check_settings(ctx)
        if self.settings[server.id][channel.id] == "off":
            await self.bot.say("Le porno est désactivé dans ce canal.")
            return
        if self.settings[server.id][channel.id] == "sfw" and self.contains_nsfw(tags):
            await self.bot.say("Bien essayé")
            return
        if tags:
            search = " ".join(tags)
        else:
            search = "random"
        msg = await self.bot.say("Chargement...")
        try:
            constructed = self.construct_url("r34", ctx, tags)
            url = constructed[0]
            filters = constructed[1]
            async with self.session.get(url) as r:
                tree = ET.fromstring(await r.read())
            results = [
            {
                    "url": str(post.attrib.get('file_url')),
                    "source": str(post.attrib.get('source'))
            } for post in tree.iter("post")
            if not any(x in post.attrib.get('tags') for x in filters) and not str(
                post.attrib.get("file_url")).endswith((".mp4", ".webm", ".swf"))
            ]
            post = choice(results)
            embed = self.r34_embed(post, search)
            await self.bot.edit_message(msg, new_content="{0.mention}:".format(user), embed=embed)
        except IndexError:
            await self.bot.edit_message(msg, "{0.mention}, Aucun résultat "
                                        "trouvé pour `{1}`".format(user, search))
        except Exception as e:
            await self.bot.edit_message(msg, "Une exception inconnue s'est produite: `{}`".format(e))

    @commands.group(pass_context=True, no_pm=True)
    async def lewdset(self, ctx):
        """Paramètres du module Lewd"""
        self.check_settings(ctx)
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return

    @checks.mod_or_permissions(manage_channels=True)
    @lewdset.command(pass_context=True, name="channel")
    async def lewdset_channel(self, ctx, mode: str):
        """Définit le mode du canal

        Off - Désactive les commandes NSFW
        SFW - Force l'affichage des images SFW
        NSFW - Autorise le NSFW"""
        server = ctx.message.server
        channel = ctx.message.channel
        valid_responses = ["off", "nsfw", "sfw"]
        r = mode.lower()
        if r not in valid_responses:
            await self.bot.send_cmd_help(ctx)
            return
        self.settings[server.id][channel.id] = r
        await self.bot.say("{0.mention} est maintenant sur le mode {1}".format(channel, r.upper()))
        dataIO.save_json("data/lewd/settings.json", self.settings)

    @lewdset.group(pass_context=True, name="filter")
    async def personal_filter(self, ctx):
        """Gestion des filtres personnels (Bloquage de certains résultats)"""
        server = ctx.message.server
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return

    @personal_filter.command(pass_context=True, name="add")
    async def filter_add(self, ctx, *tags: str):
        """Ajoute des tags au filtre personnel. Chaque tag doit être séparé par un espace"""
        if not tags:
            await self.bot.send_cmd_help(ctx)
            return
        server = ctx.message.server
        user = ctx.message.author
        added = 0
        if len(tags) + len(self.filter[server.id][user.id]) > MAX_FILTERS:
            await self.bot.say("Trop de filtres, calmez-vous un peu")
            return
        for tag in tags:
            if tag.lower() not in self.filter[server.id][user.id] and tag != "":
                self.filter[server.id][user.id].append(tag.lower())
                added += 1
        if added:
            dataIO.save_json("data/lewd/filter.json", self.filter)
            await self.bot.say("Mots ajoutés au filtre.")
        else:
            await self.bot.say("Mots déjà présent dans le filtre.")

    @personal_filter.command(pass_context=True, name="remove")
    async def filter_remove(self, ctx, *tags: str):
        """Supprime les tags du filtre personnel"""
        if not tags:
            await self.bot.send_cmd_help(ctx)
            return
        server = ctx.message.server
        user = ctx.message.author
        removed = 0
        if server.id not in self.filter:
            await self.bot.say("Il n'y a pas de tags filtrés sur ce serveur.")
            return
        if user.id not in self.filter[server.id]:
            await self.bot.say("Vous n'avez pas de tags filtrées")
            return
        for tag in tags:
            if tag.lower() in self.filter[server.id][user.id]:
                self.filter[server.id][user.id].remove(tag.lower())
                removed += 1
        if removed:
            dataIO.save_json("data/lewd/filter.json", self.filter)
            await self.bot.say("Tags supprimés du filtre.")
        else:
            await self.bot.say("Ces tags n'étaient pas dans le filtre.")

    @personal_filter.command(pass_context=True, name="show")
    async def filter_show(self, ctx):
        """Affiche votre filtre actuel"""
        server = ctx.message.server
        user = ctx.message.author
        personal_filter = ", ".join(self.filter[server.id][user.id])
        server_filter = ", ".join(self.filter[server.id]["server"])
        if not personal_filter:
            personal_filter = "None"
        if not server_filter:
            server_filter = "None"
        data = ("{0}, actuellement vous filtrez les tags suivants: `{1}`\n{2} filtre "
               "actuellement les tags suivants: `{3}`".format(
               user.mention, personal_filter, server.name, server_filter))
        await self.bot.say(data)

    @checks.mod_or_permissions(manage_channels=True)
    @lewdset.group(pass_context=True, name="serverfilter")
    async def server_filter(self, ctx):
        """Gestion du filtre serveur (Bloquage de certains résultats)"""
        server = ctx.message.server
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return

    @server_filter.command(pass_context=True, name="add")
    async def serverfilter_add(self, ctx, *tags: str):
        """Ajoute des tags au filtre du serveur. Chaque tag doit être séparé par un espace"""
        if not tags:
            await self.bot.send_cmd_help(ctx)
            return
        server = ctx.message.server
        added = 0
        if len(tags) + len(self.filter[server.id]["server"]) > MAX_FILTERS:
            await self.bot.say("Trop de filtres, calmez-vous un peu.")
            return
        for tag in tags:
            if tag.lower() not in self.filter[server.id]["server"] and tag != "":
                self.filter[server.id]["server"].append(tag.lower())
                added += 1
        if added:
            dataIO.save_json("data/lewd/filter.json", self.filter)
            await self.bot.say("Mots ajoutés au filtre.")
        else:
            await self.bot.say("Mots déjà présent dans le filtre.")

    @server_filter.command(pass_context=True, name="remove")
    async def serverfilter_remove(self, ctx, *tags: str):
        """Supprime les tags du filtre serveur"""
        if not tags:
            await self.bot.send_cmd_help(ctx)
            return
        server = ctx.message.server
        removed = 0
        if server.id not in self.filter:
            await self.bot.say("Il n'y a pas de tags filtrés sur ce serveur.")
            return
        if "server" not in self.filter[server.id]:
            await self.bot.say("Il n'y a pas de tags filtrés sur ce serveur.")
            return
        for tag in tags:
            if tag.lower() in self.filter[server.id]["server"]:
                self.filter[server.id]["server"].remove(tag.lower())
                removed += 1
        if removed:
            dataIO.save_json("data/lewd/filter.json", self.filter)
            await self.bot.say("Tags supprimés du filtre.")
        else:
            await self.bot.say("Ces tags n'étaient pas dans le filtre.")

    def e621_embed(self, post, search):
        url = post["file_url"]
        submission = "https://e621.net/post/show/" + str(post["id"])
        source = post["source"]
        if not source:
            description = "[Lien du post e621]({0})".format(submission)
        else:
            description = "[Lien du post e621]({0}) ⋅ [Source]({1})".format(submission, source)
        color = 0x152f56
        data = discord.Embed(title="Résultat de la recherche e621", colour=color,
                             description=description)
        data.set_image(url=url)
        data.set_footer(text="Résultat pour: {0}".format(search))
        return data

    def r34_embed(self, post, search):
        url = post["url"]
        source = post["source"]
        if not source:
            description = None
        else:
            description = "[Source]({0})".format(source)
        color = 0xaae5a3
        data = discord.Embed(title="Résultat de la recherche Rule34", colour=color,
                             description=description)
        data.set_image(url=url)
        data.set_footer(text="Résultat pour: {0}".format(search))
        return data

    def construct_url(self, base, ctx, text):
        server = ctx.message.server
        user = ctx.message.author
        channel = ctx.message.channel
        mode = self.settings[server.id][channel.id]
        tags = []
        filters = []
        text = [x.lower() for x in text]
        filters.extend([t.lower() for t in text if t.startswith("-")])
        text = list(set(text) - set(filters))
        if mode == "sfw":
            if not "rating:s" in tags or not "rating:safe" in tags:
                tags.append("rating:safe")
            elif not "rating:safe" in tags and base != "e621":
                tags.append("rating:safe")
        if not text and base == "e621":
            tags.append("random")
        else:
            tags.extend(text)
        if base == "e621":
            max_tags = 6
            url = "https://e621.net/post/index.json?limit=150&tags="
        else:
            max_tags = 20
            url = "https://rule34.xxx/index.php?page=dapi&s=post&q=index&tags="
        if len(tags) > max_tags:
            raise TooManyTagsError()
        filters_allowed = max_tags - len(tags)
        filters.extend(["-" + x.lower()
                        for x in self.filter[server.id]["server"]])
        filters.extend(["-" + x.lower()
                        for x in self.filter[server.id][user.id]])
        filters = list(set(filters))
        tags.extend(filters[:filters_allowed])
        del filters[:filters_allowed]
        search = "%20".join(tags)
        filters = [f.lstrip("-") for f in filters]
        return url + search, filters

    def check_settings(self, ctx):
        user = ctx.message.author
        server = ctx.message.server
        channel = ctx.message.channel
        if server.id not in self.filter:
            self.filter[server.id] = {"server": []}
            dataIO.save_json("data/lewd/filter.json", self.filter)
        if user.id not in self.filter[server.id]:
            self.filter[server.id][user.id] = []
            dataIO.save_json("data/lewd/filter.json", self.filter)
        if server.id not in self.settings:
            self.settings[server.id] = {}
            dataIO.save_json("data/lewd/settings.json", self.settings)
        if channel.id not in self.settings[server.id]:
            self.settings[server.id][channel.id] = "sfw"
            dataIO.save_json("data/lewd/settings.json", self.settings)
        return

    def contains_nsfw(self, tags):
        nsfw = ["rating:e", "rating:explicit", "rating:q", "rating:questionable"]
        if any(x in [tag.lower() for tag in tags] for x in nsfw):
            return True
        else:
            return False


def check_folders():
    folders = ("data", "data/lewd/")
    for folder in folders:
        if not os.path.exists(folder):
            print("Creating " + folder + " folder...")
            os.makedirs(folder)


def check_files():
    files = {
        "filter.json": {},
        "settings.json": {}
    }

    for filename, value in files.items():
        if not os.path.isfile("data/lewd/{}".format(filename)):
            print("Creating empty {}".format(filename))
            dataIO.save_json("data/lewd/{}".format(filename), value)


def setup(bot):
    check_folders()
    check_files()
    n = Lewd(bot)
    bot.add_cog(n)
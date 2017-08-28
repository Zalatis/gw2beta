from discord.ext import commands
from .utils import checks
from .utils.dataIO import dataIO
from datetime import datetime as dt
import asyncio
import aiohttp
import discord
import os
import calendar
import pytz


numbs = {
    "next": "➡",
    "back": "⬅",
    "exit": "❌"
}


class EventMaker():
    """Cog pour créer des events planifiés 
    dans le channel par défaut"""
    def __init__(self, bot):
        self.bot = bot
        self.events = dataIO.load_json(
            os.path.join("data", "eventmaker", "events.json"))
        self.settings = dataIO.load_json(
            os.path.join("data", "eventmaker", "settings.json"))

    async def event_menu(self, ctx, event_list: list,
                         message: discord.Message=None,
                         page=0, timeout: int=30):

        emb = event_list[page]
        if not message:
            message =\
                await self.bot.send_message(ctx.message.channel, embed=emb)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=emb)
        react = await self.bot.wait_for_reaction(
            message=message, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌"]
        )
        if react is None:
            await self.bot.remove_reaction(message, "⬅", self.bot.user)
            await self.bot.remove_reaction(message, "❌", self.bot.user)
            await self.bot.remove_reaction(message, "➡", self.bot.user)
            return None
        reacts = {v: k for k, v in numbs.items()}
        react = reacts[react.reaction.emoji]
        if react == "next":
            next_page = 0
            if page == len(event_list) - 1:
                next_page = 0  # Boucle le premier élément
            else:
                next_page = page + 1
            return await self.event_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(event_list) - 1  # Boucle le dernier élément
            else:
                next_page = page - 1
            return await self.event_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        else:
            return await\
                self.bot.delete_message(message)

    @commands.command(pass_context=True)
    async def eventcreate(self, ctx):
        """Outil de création d'événements. L'événement ne sera créé que si
        toutes les informations sont fournies correctement
        """
        author = ctx.message.author
        server = ctx.message.server
        allowed_roles = []
        server_owner = server.owner
        if server.id in self.settings:
            if self.settings[server.id]["role"] is not None:
                specified_role =\
                    [r for r in server.roles if r.id == self.settings[server.id]["role"]][0]
                allowed_roles.append(specified_role)
                allowed_roles.append(self.bot.settings.get_server_mod(server))
                allowed_roles.append(self.bot.settings.get_server_admin(server))

        if len(allowed_roles) > 0 and author != server_owner:
            for role in author.roles:
                if role in allowed_roles:
                    break
            else:
                await self.bot.say("Vous n'avez pas la permission de créer des événements!")
                return

        creation_time = dt.utcnow()
        await self.bot.say("Entrez un nom pour l'événement:")
        msg = await self.bot.wait_for_message(author=author, timeout=30)
        if msg is None:
            await self.bot.say("Aucun nom fourni!")
            return
        name = msg.content
        msg = None
        await self.bot.say(
            "Entrez dans combien de temps l'event aura lieu (exemples. 1sem, 1m 30s, 1an 2sem): ")
        msg = await self.bot.wait_for_message(author=author, timeout=30)
        if msg is None:
            await self.bot.say("Aucune heure de début prévue!")
            return
        start_time = self.parse_time(creation_time, msg)
        if start_time is None:
            await self.bot.say("Quelque chose s'est mal passé à analyser le temps que vous avez entré!")
            return
        msg = None
        await self.bot.say("Entrez une description pour l'événement: ")
        msg = await self.bot.wait_for_message(author=author, timeout=30)
        if msg is None:
            await self.bot.say("Aucune description fournie!")
            return
        if len(msg.content) > 750:
            await self.bot.say("Votre description est trop longue!")
            return
        else:
            desc = msg.content

        new_event = {
            "id": self.settings[server.id]["next_id"],
            "creator": author.id,
            "create_time": calendar.timegm(creation_time.utctimetuple()),
            "event_name": name,
            "event_start_time": start_time,
            "description": desc,
            "has_started": False,
            "participants": [author.id]
        }
        self.settings[server.id]["next_id"] += 1
        self.events[server.id].append(new_event)
        dataIO.save_json(os.path.join(
            "data", "eventmaker", "settings.json"), self.settings)
        dataIO.save_json(
            os.path.join("data", "eventmaker", "events.json"), self.events)
        emb = discord.Embed(title=new_event["event_name"],
                            description=new_event["description"],
                            url="https://time.is/et/Paris")
        emb.add_field(name="Créé par",
                      value=discord.utils.get(
                          self.bot.get_all_members(),
                          id=new_event["creator"]))
        emb.set_footer(
            text="Créer le (GMT+2) " + dt.utcfromtimestamp(
                new_event["create_time"]).strftime("%d-%m-%Y %H:%M:%S"))
        emb.add_field(name="Event ID", value=str(new_event["id"]))
        emb.add_field(
            name="Début de l'event (GMT+2)", value=dt.utcfromtimestamp(
                new_event["event_start_time"]))
        await self.bot.say(embed=emb)

    @commands.command(pass_context=True)
    async def joinevent(self, ctx, event_id: int):
        """Rejoignez l'événement spécifié"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if ctx.message.author.id not in event["participants"]:
                        event["participants"].append(ctx.message.author.id)
                        await self.bot.say("A rejoint l'event")
                        dataIO.save_json(
                            os.path.join("data", "eventmaker", "events.json"),
                            self.events)
                    else:
                        await self.bot.say("Vous avez déjà rejoint cet événement!")
                else:
                    await self.bot.say("Cet événement a déjà commencé!")
                break
        else:
            await self.bot.say("Il semble que cet événement n'existe pas!" +
                               "Peut-être a-t-il été annulé ou jamais créé?")

    @commands.command(pass_context=True)
    async def leaveevent(self, ctx, event_id: int):
        """Laissez l'événement spécifié"""
        server = ctx.message.server
        author = ctx.message.author
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if author.id in event["participants"]:
                        event["participants"].remove(author.id)
                        await self.bot.say("Vous a retiré de cet événement!")
                    else:
                        await self.bot.say(
                            "Vous n'êtes pas inscrit à cet événement!")
                else:
                    await self.bot.say("Cet événement a déjà commencé!")
                break

    @commands.command(pass_context=True)
    async def eventlist(self, ctx, *, timezone: str="UTC"):
        """Liste des événements pour ce serveur qui n'ont pas encore commencé"""
        server = ctx.message.server
        events = []
        for event in self.events[server.id]:
            if not event["has_started"]:
                emb = discord.Embed(title=event["event_name"],
                                    description=event["description"],
                                    url="https://time.is/et/Paris")
                emb.add_field(name="Créer par",
                              value=discord.utils.get(
                                  self.bot.get_all_members(),
                                  id=event["creator"]))
                emb.set_footer(
                    text="Créé le (GMT+2) " + dt.utcfromtimestamp(
                        event["create_time"]).strftime("%d-%m-%Y %H:%M:%S"))
                emb.add_field(name="Event ID", value=str(event["id"]))
                emb.add_field(
                    name="Participant count", value=str(
                        len(event["participants"])))
                emb.add_field(
                    name="Heure de début (GMT+2)", value=dt.utcfromtimestamp(
                        event["event_start_time"]))
                events.append(emb)
        if len(events) == 0:
            await self.bot.say("Aucun événement disponible!")
        else:
            await self.event_menu(ctx, events, message=None, page=0, timeout=30)

    @commands.command(pass_context=True)
    async def whojoined(self, ctx, event_id: int):
        """Liste tous les participants de l'événement"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    for user in event["participants"]:
                        user_obj = discord.utils.get(
                            self.bot.get_all_members(), id=user)
                        await self.bot.say("{}#{}".format(
                            user_obj.name, user_obj.discriminator))
                else:
                    await self.bot.say("Cet événement a déjà commencé!")
                break

    @commands.command(pass_context=True)
    async def cancelevent(self, ctx, event_id: int):
        """Annule l'événement spécifié"""
        server = ctx.message.server
        if event_id < self.settings[server.id]["next_id"]:
            to_remove =\
                [event for event in self.events[server.id] if event["id"] == event_id]
            if len(to_remove) == 0:
                await self.bot.say("Aucun événement à supprimer!")
            else:
                self.events[server.id].remove(to_remove[0])
                dataIO.save_json(
                    os.path.join("data", "eventmaker", "events.json"),
                    self.events)
                await self.bot.say("Supprime l'événement spécifié!")
        else:
            await self.bot.say("Je ne peux pas supprimer un événement qui " +
                               "n'a pas encore été créé!")

    def parse_time(self, cur_time, msg: discord.Message):
        """Analyse le temps"""
        start_time = calendar.timegm(cur_time.utctimetuple())
        content = msg.content
        pieces = content.split()
        for piece in pieces:
            if piece.endswith("an"):
                try:
                    start_time += int(piece[:-1]) * 31536000  # secondes par an
                except ValueError:
                    return None  # debug
            elif piece.endswith("sem"):
                try:
                    start_time += int(piece[:-1]) * 604800  # secondes par semaine
                except ValueError:
                    return None  # debug
            elif piece.endswith("j"):
                try:
                    start_time += int(piece[:-1]) * 86400  # secondes par jour
                except ValueError:
                    return None  # debug
            elif piece.endswith("h"):
                try:
                    start_time += int(piece[:-1]) * 3600  # secondes par heure
                except ValueError:
                    return None  # debug
            elif piece.endswith("m"):
                try:
                    start_time += int(piece[:-1]) * 60  # secondes par minute
                except ValueError:
                    return None  # debug
            elif piece.endswith("s"):
                try:
                    start_time += int(piece[:-1]) * 1  # seconde
                except ValueError:
                    return None  # debug
            else:
                return None  # debug
        return start_time

    @commands.group(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def eventset(self, ctx):
        """Paramètres des permissions"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @eventset.command(pass_context=True, name="channel")
    @checks.admin_or_permissions(manage_server=True)
    async def eventset_channel(self, ctx, channel: discord.Channel):
        """Réglez le canal utilisé pour afficher les rappels. 
        Si 'canal' est sélectionné pour les rappels sur la 
        création de l'event, ce canal
        Par défaut: le canal par défaut du serveur"""
        server = ctx.message.server
        self.settings[server.id]["channel"] = channel.id
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"),
                         self.settings)
        await self.bot.say("Canal réglé sur {}".format(channel.mention))

    @eventset.command(pass_context=True, name="role")
    @checks.admin_or_permissions(manage_server=True)
    async def eventset_role(self, ctx, *, role: str=None):
        """Définissez le rôle permettant de créer des événements. 
        Par Défaut : Tout le monde peut en créer."""
        server = ctx.message.server
        if role is not None:
            role_obj = [r for r in server.roles if r.name == role][0]
            self.settings[server.id]["role"] = role_obj.id
            dataIO.save_json(
                os.path.join("data", "eventmaker", "settings.json"),
                self.settings)
            await self.bot.say("Rôle défini pour {}".format(role))
        else:
            self.settings[server.id]["role"] = None
            dataIO.save_json(
                os.path.join("data", "eventmaker", "settings.json"),
                self.settings)
            await self.bot.say("Rôle retiré!")

    async def check_events(self):
        """Boucle d'événement"""
        CHECK_DELAY = 60
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog("EventMaker"):
            cur_time = dt.utcnow()
            cur_time = calendar.timegm(cur_time.utctimetuple())
            save = False
            for server in list(self.events.keys()):
                channel = discord.utils.get(self.bot.get_all_channels(),
                                            id=self.settings[server]["channel"])
                for event in self.events[server]:
                    if cur_time >= event["event_start_time"]\
                            and not event["has_started"]:
                        emb = discord.Embed(title=event["event_name"],
                                            description=event["description"])
                        emb.add_field(name="Créé par",
                                      value=discord.utils.get(
                                          self.bot.get_all_members(),
                                          id=event["creator"]))
                        emb.set_footer(
                            text="Créé le (GMT+2) " +
                            dt.utcfromtimestamp(
                                event["create_time"]).strftime(
                                    "%d-%m-%Y %H:%M:%S"))
                        emb.add_field(name="Event ID", value=str(event["id"]))
                        emb.add_field(
                            name="Nombre de participants", value=str(
                                len(event["participants"])))
                        try:
                            await self.bot.send_message(channel, embed=emb)
                        except discord.Forbidden:
                            pass  # Aucune autorisation pour envoyer des messages
                        for user in event["participants"]:
                            target = discord.utils.get(
                                self.bot.get_all_members(), id=user)
                            await self.bot.send_message(target, embed=emb)
                        event["has_started"] = True
                        save = True
            if save:
                dataIO.save_json(
                    os.path.join("data", "eventmaker", "events.json"),
                    self.events)
            await asyncio.sleep(CHECK_DELAY)

    async def server_join(self, server):
        if server.id not in self.settings:
            self.settings[server.id] = {
                "role": None,
                "next_id": 1,
                "channel": server.id
            }
        if server.id not in self.events:
            self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)

    async def server_leave(self, server):
        """Nettoyage après avoir quitté le serveur"""
        if server.id in self.events:
            self.events.pop(server.id)
        if server.id in self.settings:
            self.settings.pop(server.id)
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)

    async def confirm_server_setup(self):
        """Vérification des paramètres"""
        for server in list(self.bot.servers):
            if server.id not in self.settings:
                self.settings[server.id] = {
                    "role": None,
                    "next_id": 1,
                    "channel": server.id
                }
                if server.id not in self.events:
                    self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), self.settings)


def check_folder():
    if not os.path.isdir(os.path.join("data", "eventmaker")):
        print("Création du répertoire Eventmaker dans le dossier data")
        os.mkdir(os.path.join("data", "eventmaker"))


def check_file():
    if not dataIO.is_valid_json(os.path.join("data", "eventmaker", "events.json")):
        dataIO.save_json(os.path.join("data", "eventmaker", "events.json"), {})
    if not dataIO.is_valid_json(os.path.join("data", "eventmaker", "settings.json")):
        dataIO.save_json(os.path.join("data", "eventmaker", "settings.json"), {})


def setup(bot):
    check_folder()
    check_file()
    n = EventMaker(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.check_events())
    loop.create_task(n.confirm_server_setup())
    bot.add_listener(n.server_join, "on_server_join")
    bot.add_listener(n.server_leave, "on_server_remove")
    bot.add_cog(n)

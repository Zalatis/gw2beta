import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType
from .utils import checks
from .utils.timezone import get_datetime_timezoned
from .utils.timezone import get_localized_datetime

from cogs.utils.dataIO import dataIO

import os
import asyncio
import aiohttp
import re
import time
import datetime
import xml.etree.ElementTree as et
from itertools import chain
from operator import itemgetter
from motor.motor_asyncio import AsyncIOMotorClient

try:
    from bs4 import BeautifulSoup
    soupAvailable = True
except:
    soupAvailable = False

DEFAULT_HEADERS = {'User-Agent': "A GW2 Discord bot",
                   'Accept': 'application/json'}



class APIError(Exception):
    pass

class APIBadRequest(APIError):
    pass

class APIConnectionError(APIError):
    pass

class APIForbidden(APIError):
    pass

class APINotFound(APIError):
    pass

class APIKeyError(APIError):
    pass


class GuildWars2:
    """Commandes utilisant l'API GW2"""

    def __init__(self, bot):
        self.bot = bot
        self.client = AsyncIOMotorClient()
        self.db = self.client['gw2']
        self.gamedata = dataIO.load_json("data/guildwars2/gamedata.json")
        self.build = dataIO.load_json("data/guildwars2/build.json")
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.cache = dataIO.load_json("data/guildwars2/cache.json")
        self.boss_schedule = self.generate_schedule()

    def __unload(self):
        self.session.close()
        self.client.close()

    @commands.group(pass_context=True)
    async def key(self, ctx):
        """Commandes liées aux clés API"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return

    @commands.cooldown(1, 10, BucketType.user)
    @key.command(pass_context=True, name="add")
    async def key_add(self, ctx, key):
        """Ajoute votre clé API et l'associe à votre compte discord

        Pour générer une clé API,allez sur https://account.arena.net, et connectez vous.
        Cliquez sur "Applications", puis génerer une clé API, avec de préférence toutes les permissions.
        Ensuite, saisissez-le en faisant `!key add VotreClé`
        """
        server = ctx.message.server
        channel = ctx.message.channel
        user = ctx.message.author
        if server is None:
            has_permissions = False
        else:
            has_permissions = channel.permissions_for(server.me).manage_messages
        if has_permissions:
            await self.bot.delete_message(ctx.message)
            output = "Votre message a été supprimé pour cause de confidentialité"
        else:
            output = "J'aurais également supprimé votre message, mais je n'ai pas les autorisations nécessaires ..."
        if await self.fetch_key(user):
            await self.bot.say("{0.mention}, vous êtes déjà sur la liste, "
                               "retirez votre clé d'abord si vous souhaitez la modifier. {1}".format(user, output))
            return
        endpoint = "tokeninfo"
        headers = self.construct_headers(key)
        try:
            results = await self.call_api(endpoint, headers)
        except APIError as e:
            await self.bot.say("{0.mention}, {1}. {2}".format(user, "Clé invalide", output))
            return
        endpoint = "account"
        try:
            acc = await self.call_api(endpoint, headers)
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        name = results["name"]
        if not name:
            name = None  # Else embed fails
        keydoc = {
            "key": key, "_id": user.id, "account_name": acc["name"], "name": name, "permissions": results["permissions"]}
        await self.bot.say("{0.mention}, votre clé API a été vérifiée et "
                           "ajoutée à la liste. {1}".format(user, output))
        await self.db.keys.insert_one(keydoc)

    @commands.cooldown(1, 10, BucketType.user)
    @key.command(pass_context=True, name="remove")
    async def key_remove(self, ctx):
        """Supprime votre clé de la liste"""
        user = ctx.message.author
        keydoc = await self.fetch_key(user)
        if keydoc:
            await self.db.keys.delete_one({"_id": user.id})
            await self.bot.say("{0.mention}, votre clé a été retiré avec succès "
                               "Vous pouvez en entrer une nouvelle.".format(user))
        else:
            await self.bot.say("{0.mention}, Aucune clé API associée à votre compte. "
                               "Ajoutez votre clé en utilisant la commande `!key add`.".format(user))

    @commands.cooldown(1, 10, BucketType.user)
    @key.command(pass_context=True, name="info")
    async def key_info(self, ctx):
        """Informations sur votre clé API
        Nécessite une clé
        """
        user = ctx.message.author
        scopes = []
        endpoint = "account"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound:
            await self.bot.say("Nom de personnage invalide")
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        accountname = results["name"]
        keyname = keydoc["name"]
        permissions = keydoc["permissions"]
        permissions = ', '.join(permissions)
        color = self.getColor(user)
        data = discord.Embed(description=None, colour=color)
        if keyname:
            data.add_field(name="Key name", value=keyname)
        data.add_field(name="Permissions", value=permissions)
        data.set_author(name=accountname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 10, BucketType.user)
    @commands.command(pass_context=True)
    async def account(self, ctx):
        """Informations sur votre compte
        Nécessite une clé avec la permission `account`
        """
        user = ctx.message.author
        scopes = ["account"]
        endpoint = "account"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        accountname = keydoc["account_name"]
        created = results["created"].split("T", 1)[0]
        hascommander = "Oui" if results["commander"] else "Non"
        color = self.getColor(user)
        data = discord.Embed(description=None, colour=color)
        data.add_field(name="Compte créer le (Format:AAAA-MM-JJ)", value=created)
        data.add_field(name="A le tag 'commandant'",
                       value=hascommander, inline=False)
        if "fractal_level" in results:
            fractallevel = results["fractal_level"]
            data.add_field(name="Niveau Fractal", value=fractallevel)
        if "wvw_rank" in results:
            wvwrank = results["wvw_rank"]
            data.add_field(name="Rang McM", value=wvwrank)
        if "pvp" in keydoc["permissions"]:
            endpoint = "pvp/stats"
            try:
                pvp = await self.call_api(endpoint, headers)
            except APIError as e:
                await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                                   "`{1}`".format(user, e))
                return
            pvprank = pvp["pvp_rank"] + pvp["pvp_rank_rollovers"]
            data.add_field(name="Rang PvP", value=pvprank)
        data.set_author(name=accountname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 60, BucketType.user)
    @commands.command(pass_context=True)
    async def li(self, ctx):
        """Montre combien de connaissances légendaires vous avez
        Nécessite une clé avec les persmissions 'inventories' et 'characters'
        """
        user = ctx.message.author
        scopes = ["inventories", "characters"]
        keydoc = await self.fetch_key(user)
        msg = await self.bot.say("Obtention des connaissances légendaires, cela peut prendre un certain temps ...")
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            endpoint_bank = "account/bank"
            endpoint_material = "account/materials"
            endpoint_shared = "account/inventory"
            endpoint_char = "characters?page=0"
            bank = await self.call_api(endpoint_bank, headers)
            materials = await self.call_api(endpoint_material, headers)
            shared = await self.call_api(endpoint_shared, headers)
            characters = await self.call_api(endpoint_char, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return

        # Items to look for
        ids = self.gamedata.get("insights")
        id_legendary_insight = ids.get("legendary_insight")
        id_gift_of_prowess = ids.get("gift_of_prowess")
        id_envoy_insignia = ids.get("envoy_insignia")
        ids_refined_envoy_armor = set(ids.get("refined_envoy_armor").values())
        ids_perfected_envoy_armor = set(ids.get("perfected_envoy_armor").values())

        # Filter empty slots and uninteresting items out of the inventories.
        #
        # All inventories are converted to lists as they are used multiple
        # times. If they stay as generators, the first scan on each will exhaust
        # them, resulting in empty results for later scans (this was really hard
        # to track down, since the scans are also generators, so the order of
        # access to an inventory is not immediately obvious in the code).
        __pre_filter = ids_perfected_envoy_armor.union(
            {id_legendary_insight, id_gift_of_prowess, id_envoy_insignia},
            ids_refined_envoy_armor)
        # If an item slot is empty, or the item is not interesting, filter it out.
        pre_filter = lambda a, b=__pre_filter: a is not None and a["id"] in b
        inv_bank = list(filter(pre_filter, bank))
        del bank # We don't need these anymore, free them.

        inv_materials = list(filter(pre_filter, materials))
        del materials

        inv_shared = list(filter(pre_filter, shared))
        del shared


        # Bags have multiple inventories for each character, so:
        # Step 5: Discard the empty and uninteresting
        inv_bags = list(filter(pre_filter,
            # Step 4: Flatten!
            chain.from_iterable(
                # Step 3: Flatten.
                chain.from_iterable(
                    # Step 2: Get inventories from each existing bag
                    (map(itemgetter("inventory"), filter(None, bags)) for bags in
                        # Step 1: Get all bags
                        map(itemgetter("bags"), characters))))))
        # Now we have a simple list of items in all bags on all characters.

        # Step 3: Discard empty and uninteresting
        equipped = list(filter(pre_filter,
            # Step 2: Flatten
            chain.from_iterable(
                # Step 1: get all character equipment
                map(itemgetter("equipment"), characters))))
        del characters
        # Like the bags, we now have a simple list of character gear

        # Filter out items that don't match the ones we want.
        # Step 1: Define a test function for filter(). The id is passed in with
        #         an optional argument to avoid any potential issues with scope.
        li_scan = lambda a, b=id_legendary_insight: a["id"] == b
        # Step 2: Filter out all items we don't care about
        # Step 3: Extract the `count` field.
        li_bank = map(itemgetter("count"), filter(li_scan, inv_bank))
        li_materials = map(itemgetter("count"), filter(li_scan, inv_materials))
        li_shared = map(itemgetter("count"), filter(li_scan, inv_shared))
        li_bags = map(itemgetter("count"), filter(li_scan, inv_bags))

        prowess_scan = lambda a, b=id_gift_of_prowess: a["id"] == b
        prowess_bank = map(itemgetter("count"), filter(prowess_scan, inv_bank))
        prowess_shared = map(itemgetter("count"), filter(prowess_scan, inv_shared))
        prowess_bags = map(itemgetter("count"), filter(prowess_scan, inv_bags))

        insignia_scan = lambda a, b=id_envoy_insignia: a["id"] == b
        insignia_bank = map(itemgetter("count"), filter(insignia_scan, inv_bank))
        insignia_shared = map(itemgetter("count"), filter(insignia_scan, inv_shared))
        insignia_bags = map(itemgetter("count"), filter(insignia_scan, inv_bags))

        # This one is slightly different: since we are matching against a set
        # of ids, we use `in` instead of a simple comparison.
        perfect_armor_scan = lambda a, b=ids_perfected_envoy_armor: a["id"] in b
        perfect_armor_bank = map(itemgetter("count"), filter(perfect_armor_scan, inv_bank))
        perfect_armor_shared = map(itemgetter("count"), filter(perfect_armor_scan, inv_shared))
        perfect_armor_bags = map(itemgetter("count"), filter(perfect_armor_scan, inv_bags))
        # immediately converting this to a list because we'll need the length
        # later and that would exhaust the generator, resulting in surprises if
        # it's used more later.
        perfect_armor_equipped = list(filter(perfect_armor_scan, equipped))

        # Repeat for Refined Armor
        refined_armor_scan = lambda a, b=ids_refined_envoy_armor: a["id"] in b
        refined_armor_bank = map(itemgetter("count"), filter(refined_armor_scan, inv_bank))
        refined_armor_shared = map(itemgetter("count"), filter(refined_armor_scan, inv_shared))
        refined_armor_bags = map(itemgetter("count"), filter(refined_armor_scan, inv_bags))
        refined_armor_equipped = list(filter(refined_armor_scan, equipped))

        # Now that we have all the items we are interested in, it's time to
        # count them! Easy enough to just `sum` the `chain`.
        sum_li = sum(chain(li_bank, li_materials, li_bags, li_shared))
        sum_prowess  = sum(chain(prowess_bank, prowess_shared, prowess_bags))
        sum_insignia = sum(chain(insignia_bank, insignia_shared, insignia_bags))
        # Armor is a little different. The ones in inventory have a count like
        # the other items, but the ones equipped don't, so we can just take the
        # length of the list there.
        sum_refined_armor = sum(chain(refined_armor_bank, refined_armor_shared, refined_armor_bags)) + len(refined_armor_equipped)
        sum_perfect_armor = sum(chain(perfect_armor_bank, perfect_armor_shared, perfect_armor_bags)) + len(perfect_armor_equipped)

        # LI is fine, but the others are composed of 25 or 50 LIs.
        li_prowess = sum_prowess * 25
        li_insignia = sum_insignia * 25
        # Refined Envoy Armor. First set is free!
        # But, keeping track of it is troublesome. What we do is add up to 6
        # perfected armor pieces to this (the ones that used the free set), but
        # not more (`min()`).
        # Then, subtract 6 for the free set. If one full set of perfected armor
        # has been crafted, then we have just the count of refined armor. This
        # is exactly what we want, because the free set is now being counted by
        # `li_perfect_armor`.
        li_refined_armor = max(min(sum_perfect_armor, 6) + sum_refined_armor - 6, 0) * 25
        # Perfected Envoy Armor. First set is half off!
        li_perfect_armor = min(sum_perfect_armor, 6) * 25 + max(sum_perfect_armor - 6, 0) * 50
        # Stagger the calculation for detail later.
        crafted_li = li_prowess + li_insignia + li_perfect_armor + li_refined_armor
        total_li = sum_li + crafted_li

        # Construct an embed object for better formatting of our data
        embed = discord.Embed()
        # Right up front, the information everyone wants:
        embed.title = "{0} Connaissances légendaire gagnées".format(total_li)
        # Identify the user that asked
        embed.set_author(name=user.name, icon_url=user.avatar_url)
        # LI icon as thumbnail looks pretty cool.
        embed.set_thumbnail(url="https://render.guildwars2.com/file/6D33B7387BAF2E2CC9B5D37D1D1B01246AB6FA22/1302744.png")
        # Legendary color!
        embed.colour = 0x4C139D
        # Quick breakdown. No detail on WHERE all those LI are. That's for $search.
        embed.description = "{1} à portée de main, {2} utilisé dans l'artisanat".format(total_li, sum_li, crafted_li)
        # Save space by skipping empty sections
        if sum_perfect_armor:
            embed.add_field(
                name="{0} Pièce(s) d'armure d'émissaire perfectionnée".format(sum_perfect_armor),
                value="Représentant {0} connaissances légendaire".format(li_perfect_armor),
                inline=False)
        if sum_refined_armor:
            embed.add_field(
                name="{0} Pièce(s) d'armures raffinée".format(sum_refined_armor),
                value="Représentant {0} connaissances légendaire".format(li_refined_armor),
                inline=False)
        if sum_prowess:
            embed.add_field(
                name="{0} Don(s) de prouesse".format(sum_prowess),
                value="Représentant {0} connaissances légendaire".format(li_prowess),
                inline=False)
        if sum_insignia:
            embed.add_field(
                name="{0} Insigne d'émissaire".format(sum_insignia),
                value="Représentant {0} connaissances légendaire".format(li_insignia),
                inline=False)
        # Identify the bot
        embed.set_footer(text=self.bot.user.name, icon_url=self.bot.user.avatar_url)

        # Edit the embed into the initial message.
        await self.bot.edit_message(msg, "{0.mention}, voici vos connaissances légendaire".format(user), embed=embed)

    @commands.group(pass_context=True)
    async def character(self, ctx):
        """Commandes liées au personnage
        Nécessite une clé API avec la permission 'characters'
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 5, BucketType.user)
    @character.command(name="info", pass_context=True)
    async def character_info(self   , ctx, *, character: str):
        """Informations sur le personnage donné
        Vous devez être le propriétaire du personnage donné.
        Nécessite une clé API avec la permission `characters`
        """
        scopes = ["characters"]
        user = ctx.message.author
        character = character.title()
        character.replace(" ", "%20")
        endpoint = "characters/{0}".format(character)
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound:
            await self.bot.say("Nom du personnage invalide")
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        accountname = keydoc["account_name"]
        age = self.get_age(results["age"])
        created = results["created"].split("T", 1)[0]
        deaths = results["deaths"]
        deathsperhour = round(deaths / (results["age"] / 3600), 1)
        if "title" in results:
            title = await self._get_title_(results["title"])
        else:
            title = None
        gender = results["gender"]
        profession = results["profession"]
        race = results["race"]
        guild = results["guild"]
        color = self.gamedata["professions"][profession.lower()]["color"]
        color = int(color, 0)
        icon = self.gamedata["professions"][profession.lower()]["icon"]
        data = discord.Embed(description=title, colour=color)
        data.set_thumbnail(url=icon)
        data.add_field(name="Créer le", value=created)
        data.add_field(name="Temps de jeu", value=age)
        if guild is not None:
            guild = await self._get_guild_(results["guild"])
            gname = guild["name"]
            gtag = guild["tag"]
            data.add_field(name="Guilde", value="[{0}] {1}".format(gtag, gname))
        data.add_field(name="Morts", value=deaths)
        data.add_field(name="Morts par heure", value=str(deathsperhour))
        data.set_author(name=character)
        data.set_footer(text="A {0} {1} {2}".format(
            gender.lower(), race.lower(), profession.lower()))
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 30, BucketType.user)
    @character.command(name="list", pass_context=True)
    async def character_list(self, ctx):
        """Liste tous vos personnages
        Nécessite une clé API avec la permission `characters`
        """
        user = ctx.message.author
        scopes = ["characters"]
        endpoint = "characters?page=0"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        output = "{0.mention}, Vos personnages: ```"
        for x in results:
            output += "\n" + x["name"] + " (" + x["profession"] + ")"
        output += "```"
        await self.bot.say(output.format(user))

    @commands.cooldown(1, 10, BucketType.user)
    @character.command(pass_context=True, name="gear")
    async def character_gear(self, ctx, *, character: str):
        """Affiche l'equipement d'un personnage donné
        Vous devez être le propriétaire du personnage donné.
        Nécessite une clé API avec la permission `characters`
        """
        user = ctx.message.author
        scopes = ["characters"]
        character = character.title()
        character.replace(" ", "%20")
        endpoint = "characters/{0}".format(character)
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound:
            await self.bot.say("Nom du personnage invalide".format(user))
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
        eq = results["equipment"]
        gear = {}
        pieces = ["Helm", "Shoulders", "Coat", "Gloves", "Leggings", "Boots", "Ring1", "Ring2", "Amulet",
                  "Accessory1", "Accessory2", "Backpack", "WeaponA1", "WeaponA2", "WeaponB1", "WeaponB2"]
        for piece in pieces:
            gear[piece] = {"id": None, "upgrades": [], "infusions": [],
                           "stat": None, "name": None}
        for item in eq:
            for piece in pieces:
                if item["slot"] == piece:
                    gear[piece]["id"] = item["id"]
                    c = await self.fetch_item(item["id"])
                    gear[piece]["name"] = c["name"]
                    if "upgrades" in item:
                        for u in item["upgrades"]:
                            upgrade = await self.db.items.find_one({"_id": u})
                            gear[piece]["upgrades"].append(upgrade["name"])
                    if "infusions" in item:
                        for u in item["infusions"]:
                            infusion = await self.db.items.find_one({"_id": u})
                            gear[piece]["infusions"].append(infusion["name"])
                    if "stats" in item:
                        gear[piece]["stat"] = await self.fetch_statname(item["stats"]["id"])
                    else:
                        thing = await self.db.items.find_one({"_id": item["id"]})
                        try:
                            statid = thing["details"]["infix_upgrade"]["id"]
                            gear[piece]["stat"] = await self.fetch_statname(statid)
                        except:
                            gear[piece]["stat"] = ""
        profession = results["profession"]
        level = results["level"]
        color = self.gamedata["professions"][profession.lower()]["color"]
        icon = self.gamedata["professions"][profession.lower()]["icon"]
        color = int(color, 0)
        data = discord.Embed(description="Gear", colour=color)
        for piece in pieces:
            if gear[piece]["id"] is not None:
                statname = gear[piece]["stat"]
                itemname = gear[piece]["name"]
                upgrade = self.handle_duplicates(gear[piece]["upgrades"])
                infusion = self.handle_duplicates(gear[piece]["infusions"])
                msg = "\n".join(upgrade + infusion)
                if not msg:
                    msg = "---"
                data.add_field(name="{0} {1} [{2}]".format(
                    statname, itemname, piece), value=msg, inline=False)
        data.set_author(name=character)
        data.set_footer(text="A level {0} {1} ".format(
            level, profession.lower()), icon_url=icon)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException as e:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.group(pass_context=True)
    async def wallet(self, ctx):
        """Commandes liées au portefeuille
        Nécessite une clé API avec la permission 'wallet'
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 10, BucketType.user)
    @wallet.command(pass_context=True, name="currencies")
    async def wallet_currencies(self, ctx):
        """Renvoie une liste de toutes les devises"""
        user = ctx.message.author
        cursor = self.db.currencies.find()
        results = []
        async for x in cursor:
            results.append(x)
        currlist = [currency["name"] for currency in results]
        output = "Les devises disponibles sont: ```"
        output += ", ".join(currlist) + "```"
        await self.bot.say(output)

    @commands.cooldown(1, 5, BucketType.user)
    @wallet.command(pass_context=True, name="currency")
    async def wallet_currency(self, ctx, *, currency: str):
        """Info à propos des devises. Utilisez `!wallet currencies` pour avoir une liste"""
        user = ctx.message.author
        cursor = self.db.currencies.find()
        results = []
        async for x in cursor:
            results.append(x)
        if currency.lower() == "gold":
            currency = "coin"
        cid = None
        for curr in results:
            if curr["name"].lower() == currency.lower():
                cid = curr["id"]
                desc = curr["description"]
                icon = curr["icon"]
        if not cid:
            await self.bot.say("Devise non valide. Voir `!wallet currencies`")
            return
        color = self.getColor(user)
        data = discord.Embed(description="Currency", colour=color)
        scopes = ["wallet"]
        endpoint = "account/wallet"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            wallet = await self.call_api(endpoint, headers)
            for item in wallet:
                if item["id"] == 1 and cid == 1:
                    count = self.gold_to_coins(item["value"])
                elif item["id"] == cid:
                    count = item["value"]
            data.add_field(name="Count", value=count, inline=False)
        except:
            pass
        data.set_thumbnail(url=icon)
        data.add_field(name="Description", value=desc, inline=False)
        data.set_author(name=currency.title())
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 5, BucketType.user)
    @wallet.command(pass_context=True, name="show")
    async def wallet_show(self, ctx):
        """Montre les monnaies les plus importantes dans votre portefeuille
        Nécessite une clé API avec la permission `wallet`
        """
        user = ctx.message.author
        scopes = ["wallet"]
        endpoint = "account/wallet"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        wallet = [{"count": 0, "id": 1, "name": "PO"},
                  {"count": 0, "id": 4, "name": "Gemmes"},
                  {"count": 0, "id": 2, "name": "Karma"},
                  {"count": 0, "id": 3, "name": "Lauriers"},
                  {"count": 0, "id": 18, "name": "Charges de transmutation"},
                  {"count": 0, "id": 23, "name": "Éclat d'esprit"},
                  {"count": 0, "id": 32, "name": "Magie déliée"},
                  {"count": 0, "id": 15, "name": "Insigne d'honneur"},
                  {"count": 0, "id": 16, "name": "Recommandation de guilde"}]
        for x in wallet:
            for curr in results:
                if curr["id"] == x["id"]:
                    x["count"] = curr["value"]
        accountname = keydoc["account_name"]
        color = self.getColor(user)
        data = discord.Embed(description="Wallet", colour=color)
        for x in wallet:
            if x["name"] == "PO":
                x["count"] = self.gold_to_coins(x["count"])
                data.add_field(name=x["name"], value=x["count"], inline=False)
            elif x["name"] == "Gemmes":
                data.add_field(name=x["name"], value=x["count"], inline=False)
            else:
                data.add_field(name=x["name"], value=x["count"])
        data.set_author(name=accountname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 5, BucketType.user)
    @wallet.command(pass_context=True, name="tokens")
    async def wallet_tokens(self, ctx):
        """Affiche les devises spécifiques aux instances
        Nécessite une clé API avec la permission `wallet`
        """
        user = ctx.message.author
        scopes = ["wallet"]
        endpoint = "account/wallet"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        wallet = [{"count": 0, "id": 5, "name": "Larme ascalonienne"},
                  {"count": 0, "id": 6, "name": "Eclat de Zhaïtan"},
                  {"count": 0, "id": 9, "name": "Sceau de Beetletun"},
                  {"count": 0, "id": 10, "name": "Manifeste du taupinariat"},
                  {"count": 0, "id": 11, "name": "Pousse mortelle"},
                  {"count": 0, "id": 12, "name": "Symbole de Koda"},
                  {"count": 0, "id": 13, "name": "Gravure de Charr de la Légion de la Flamme"},
                  {"count": 0, "id": 14, "name": "Cristal de connaissance"},
                  {"count": 0, "id": 7, "name": "Relique fractale"},
                  {"count": 0, "id": 24, "name": "Relique fractale immaculée"},
                  {"count": 0, "id": 28, "name": "Éclat de magnétite"}]
        for x in wallet:
            for curr in results:
                if curr["id"] == x["id"]:
                    x["count"] = curr["value"]
        accountname = keydoc["account_name"]
        color = self.getColor(user)
        data = discord.Embed(description="Tokens", colour=color)
        for x in wallet:
            if x["name"] == "Éclat de magnétite":
                data.add_field(name=x["name"], value=x["count"], inline=False)
            else:
                data.add_field(name=x["name"], value=x["count"])
        data.set_author(name=accountname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 5, BucketType.user)
    @wallet.command(pass_context=True, name="maps")
    async def wallet_maps(self, ctx):
        """Affiche les devises spécifiques à la carte
        Nécessite une clé API avec la permission `wallet`
        """
        user = ctx.message.author
        scopes = ["wallet"]
        endpoint = "account/wallet"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        wallet = [{"count": 0, "id": 25, "name": "Géodes"},
                  {"count": 0, "id": 27, "name": "Écu de bandit"},
                  {"count": 0, "id": 19, "name": "Pièce d'aéronef"},
                  {"count": 0, "id": 22, "name": "Bloc d'aurillium"},
                  {"count": 0, "id": 20, "name": "Cristaux des lignes de force"},
                  {"count": 0, "id": 32, "name": "Magie déliée"}]
        for x in wallet:
            for curr in results:
                if curr["id"] == x["id"]:
                    x["count"] = curr["value"]
        accountname = keydoc["account_name"]
        color = self.getColor(user)
        data = discord.Embed(description="Tokens", colour=color)
        for x in wallet:
            data.add_field(name=x["name"], value=x["count"])
        data.set_author(name=accountname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.group(pass_context=True)
    async def guild(self, ctx):
        """Commandes liées à la guilde.
        Nécessite une clé API avec la permission `guild`
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 20, BucketType.user)
    @guild.command(pass_context=True, name="info")
    async def guild_info(self, ctx, *, guild_name: str):
        """Informations sur les statistiques générales de guilde
        Entrez le nom de la guilde
        Nécessite une clé API avec la permission `guild`
        """
        user = ctx.message.author
        color = self.getColor(user)
        guild = guild_name.replace(' ', '%20')
        scopes = ["guilds"]
        endpoint_id = "guild/search?name={0}".format(guild)
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            guild_id = await self.call_api(endpoint_id)
            guild_id = str(guild_id).strip("['")
            guild_id = str(guild_id).strip("']")
            endpoint = "guild/{0}".format(guild_id)
            results = await self.call_api(endpoint, headers)
        except APINotFound:
            await self.bot.say("Nom de guilde invalide")
            return
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        level = results["level"]
        name = results["name"]
        tag = results["tag"]
        member_cap = results["member_capacity"]
        influence = results["influence"]
        aetherium = results["aetherium"]
        resonance = results["resonance"]
        favor = results["favor"]
        member_count = results["member_count"]
        data = discord.Embed(
            description='Informations générales sur votre guilde', colour=color)
        data.set_author(name=name + " [" + tag + "]")
        data.add_field(name='Influence', value=influence, inline=True)
        data.add_field(name='Étherium', value=aetherium, inline=True)
        data.add_field(name='Resonance', value=resonance, inline=True)
        data.add_field(name='Faveur', value=favor, inline=True)
        data.add_field(name='Membres', value=str(
            member_count) + "/" + str(member_cap), inline=True)
        if "motd" in results:
            motd = results["motd"]
            data.add_field(name='Message du jour:', value=motd, inline=False)
        data.set_footer(text='Guilde niveau {0}'.format(level))
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 20, BucketType.user)
    @guild.command(pass_context=True, name="members")
    async def guild_members(self, ctx, *, guild_name: str):
        """Donne la liste de tous les membres ainsi que leurs rangs
        Nécessite une clé API avec la permission `guilds` ainsi que d'avoir les droits de chef de guilde"""
        user = ctx.message.author
        color = self.getColor(user)
        guild = guild_name.replace(' ', '%20')
        scopes = ["guilds"]
        endpoint_id = "guild/search?name={0}".format(guild)
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            guild_id = await self.call_api(endpoint_id)
            guild_id = str(guild_id).strip("['")
            guild_id = str(guild_id).strip("']")
            endpoint = "guild/{0}/members".format(guild_id)
            endpoint_ranks = "guild/{0}/ranks".format(guild_id)
            ranks = await self.call_api(endpoint_ranks, headers)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound:
            await self.bot.say("Nom de guilde invalide")
            return
        except APIForbidden:
            await self.bot.say("Vous devez être chef de guilde pour utiliser cette commande")
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        guild = guild.replace('%20', ' ')
        data = discord.Embed(description='Membre {0}'.format(
            guild.title()), colour=color)
        data.set_author(name=guild.title())
        counter = 0
        order_id = 1
        # For each order the rank has, go through each member and add it with
        # the current order increment to the embed
        for order in ranks:
            for member in results:
                # Filter invited members
                if member['rank'] != "invité":
                    member_rank = member['rank']
                    # associate order from /ranks with rank from /members
                    for rank in ranks:
                        if member_rank == rank['id']:
                            # await self.bot.say('DEBUG: ' + member['name'] + '
                            # has rank ' + member_rank + ' and rank has order '
                            # + str(rank['order']))
                            if rank['order'] == order_id:
                                if counter < 20:
                                    data.add_field(
                                        name=member['name'], value=member['rank'])
                                    counter += 1
            order_id += 1
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 20, BucketType.user)
    @guild.command(pass_context=True, name="treasury")
    async def guild_treasury(self, ctx, *, guild_name: str):
        """Donne une liste des éléments actuels et nécessaires pour les mises à niveau
           Nécessite une clé API avec la permission `guilds` ainsi que d'avoir les droits de chef de guilde"""
        user = ctx.message.author
        color = self.getColor(user)
        guild = guild_name.replace(' ', '%20')
        scopes = ["guilds"]
        endpoint_id = "guild/search?name={0}".format(guild)
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            guild_id = await self.call_api(endpoint_id)
            guild_id = str(guild_id).strip("['")
            guild_id = str(guild_id).strip("']")
            endpoint = "guild/{0}/treasury".format(guild_id)
            treasury = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound:
            await self.bot.say("Nom de guilde invalide")
            return
        except APIForbidden:
            await self.bot.say("Vous n'avez pas assez de permissions dans la guilde pour cette commande")
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        guild = guild.replace('%20', ' ')
        data = discord.Embed(description='Contenu du trésor: {0}'.format(
            guild.title()), colour=color)
        data.set_author(name=guild.title())
        counter = 0
        item_counter = 0
        amount = 0
        item_id = ""
        itemlist = []
        for item in treasury:
            res = await self.db.items.find_one({"_id": item["item_id"]})
            itemlist.append(res)
        # Collect amounts
        if treasury:
            for item in treasury:
                if counter < 20:
                    current = item["count"]
                    item_name = itemlist[item_counter]["name"]
                    needed = item["needed_by"]
                    for need in needed:
                        amount = amount + need["count"]
                    if amount != current:
                        data.add_field(name=item_name, value=str(
                            current) + "/" + str(amount), inline=True)
                        counter += 1
                    amount = 0
                    item_counter += 1
        else:
            await self.bot.say("Le Trésor est vide!")
            return
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.group(pass_context=True)
    async def pvp(self, ctx):
        """Commandes liées au PvP.
        Nécessite une clé API avec la permission 'pvp'
        """
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 20, BucketType.user)
    @pvp.command(pass_context=True, name="stats")
    async def pvp_stats(self, ctx):
        """Informations sur vos statistiques générales de PvP
        Nécessite une clé API avec la permission `pvp`
        """
        user = ctx.message.author
        scopes = ["pvp"]
        endpoint = "pvp/stats"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        accountname = keydoc["account_name"]
        pvprank = results["pvp_rank"] + results["pvp_rank_rollovers"]
        totalgamesplayed = sum(results["aggregate"].values())
        totalwins = results["aggregate"]["wins"] + results["aggregate"]["byes"]
        if totalgamesplayed != 0:
            totalwinratio = int((totalwins / totalgamesplayed) * 100)
        else:
            totalwinratio = 0
        rankedgamesplayed = sum(results["ladders"]["ranked"].values())
        rankedwins = results["ladders"]["ranked"]["wins"] + \
            results["ladders"]["ranked"]["byes"]
        if rankedgamesplayed != 0:
            rankedwinratio = int((rankedwins / rankedgamesplayed) * 100)
        else:
            rankedwinratio = 0
        rank_id = results["pvp_rank"] // 10 + 1
        endpoint_ranks = "pvp/ranks/{0}".format(rank_id)
        try:
            rank = await self.call_api(endpoint_ranks)
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        rank_icon = rank["icon"]
        color = self.getColor(user)
        data = discord.Embed(description=None, colour=color)
        data.add_field(name="Rang", value=pvprank, inline=False)
        data.add_field(name="Total de parties jouées", value=totalgamesplayed)
        data.add_field(name="Total de victoires", value=totalwins)
        data.add_field(name="WinRatio Total",
                       value="{}%".format(totalwinratio))
        data.add_field(name="Parties classées jouées", value=rankedgamesplayed)
        data.add_field(name="Classées gagnées", value=rankedwins)
        data.add_field(name="WinRatio des classées",
                       value="{}%".format(rankedwinratio))
        data.set_author(name=accountname)
        data.set_thumbnail(url=rank_icon)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("L'API a répondu avec l'erreur suivante:")

    @commands.cooldown(1, 5, BucketType.user)
    @pvp.command(pass_context=True, name="professions")
    async def pvp_professions(self, ctx, *, profession: str=None):
        """Informations sur vos statistiques par profression en PvP.
        Si aucune profession n'est donnée, par défaut, donne les statistiques générales.
        Exemple: `!pvp professions <profession>`
        """
        user = ctx.message.author
        professionsformat = {}
        scopes = ["pvp"]
        endpoint = "pvp/stats"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        accountname = keydoc["account_name"]
        professions = self.gamedata["professions"].keys()
        if not profession:
            for profession in professions:
                if profession in results["professions"]:
                    wins = results["professions"][profession]["wins"] + \
                        results["professions"][profession]["byes"]
                    total = sum(results["professions"][profession].values())
                    winratio = int((wins / total) * 100)
                    professionsformat[profession] = {
                        "wins": wins, "total": total, "winratio": winratio}
            mostplayed = max(professionsformat,
                             key=lambda i: professionsformat[i]['total'])
            icon = self.gamedata["professions"][mostplayed]["icon"]
            mostplayedgames = professionsformat[mostplayed]["total"]
            highestwinrate = max(
                professionsformat, key=lambda i: professionsformat[i]["winratio"])
            highestwinrategames = professionsformat[highestwinrate]["winratio"]
            leastplayed = min(professionsformat,
                              key=lambda i: professionsformat[i]["total"])
            leastplayedgames = professionsformat[leastplayed]["total"]
            lowestestwinrate = min(
                professionsformat, key=lambda i: professionsformat[i]["winratio"])
            lowestwinrategames = professionsformat[lowestestwinrate]["winratio"]
            color = self.getColor(user)
            data = discord.Embed(description="Professions", colour=color)
            data.set_thumbnail(url=icon)
            data.add_field(name="Profession la plus jouée", value="{0}, avec {1} parties".format(
                mostplayed.capitalize(), mostplayedgames))
            data.add_field(name="Profession avec le plus haut ratio de victoire", value="{0}, avec {1}%".format(
                highestwinrate.capitalize(), highestwinrategames))
            data.add_field(name="Profession la moins jouée", value="{0}, avec {1} partie(s)".format(
                leastplayed.capitalize(), leastplayedgames))
            data.add_field(name="Profession avec le plus bas ratio de victoire", value="{0}, avec {1}%".format(
                lowestestwinrate.capitalize(), lowestwinrategames))
            data.set_author(name=accountname)
            data.set_footer(text="PROTIP: Utilise `!pvp professions <profession>` pour "
                            "plus de détails sur les stats")
            try:
                await self.bot.say(embed=data)
            except discord.HTTPException:
                await self.bot.say("Besoin d'autorisation pour intégrer des liens")
        elif profession.lower() not in self.gamedata["professions"]:
            await self.bot.say("Profession Invalide")
        elif profession.lower() not in results["professions"]:
            await self.bot.say("Vous n'avez pas joué cette profession!")
        else:
            prof = profession.lower()
            wins = results["professions"][prof]["wins"] + \
                results["professions"][prof]["byes"]
            total = sum(results["professions"][prof].values())
            winratio = int((wins / total) * 100)
            color = self.gamedata["professions"][prof]["color"]
            color = int(color, 0)
            data = discord.Embed(
                description="Stats for {0}".format(prof), colour=color)
            data.set_thumbnail(url=self.gamedata["professions"][prof]["icon"])
            data.add_field(name="Total de parties jouées",
                           value="{0}".format(total))
            data.add_field(name="Wins", value="{0}".format(wins))
            data.add_field(name="Winratio",
                           value="{0}%".format(winratio))
            data.set_author(name=accountname)
            try:
                await self.bot.say(embed=data)
            except discord.HTTPException:
                await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.cooldown(1, 10, BucketType.user)
    @commands.command(pass_context=True)
    async def bosses(self, ctx):
        """Liste tous les boss que vous avez tués cette semaine
        Nécessite une clé API avec la permission 'progression'
        """
        user = ctx.message.author
        scopes = ["progression"]
        endpoint = "account/raids"
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            results = await self.call_api(endpoint, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        else:
            newbosslist = list(
                set(list(self.gamedata["bosses"])) ^ set(results))
            if not newbosslist:
                await self.bot.say("Félicitations {0.mention}, "
                                   "Vous les avez tous battus. Voici une étoile d'or: "
                                   ":star:".format(user))
            else:
                formattedlist = []
                output = "{0.mention}, Vous n'avez pas tué les boss suivants cette semaine: ```"
                newbosslist.sort(
                    key=lambda val: self.gamedata["bosses"][val]["order"])
                for boss in newbosslist:
                    formattedlist.append(self.gamedata["bosses"][boss]["name"])
                for x in formattedlist:
                    output += "\n" + x
                output += "```"
                await self.bot.say(output.format(user))

    @commands.group(pass_context=True)
    async def wvw(self, ctx):
        """Commande liée au McM"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 20, BucketType.user)
    @wvw.command(pass_context=True, name="worlds")
    async def wvw_worlds(self, ctx):
        """Liste tous les mondes
        """
        user = ctx.message.author
        try:
            endpoint = "worlds?ids=all"
            results = await self.call_api(endpoint)
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        output = "Les mondes disponibles sont: ```"
        for world in results:
            output += world["name"] + ", "
        output += "```"
        await self.bot.say(output)

    @commands.cooldown(1, 10, BucketType.user)
    @wvw.command(pass_context=True, name="info")
    async def wvw_info(self, ctx, *, world: str=None):
        """Informations sur un monde. Si aucun n'est fourni, le monde du compte sera utilisé par défaut.
        """
        user = ctx.message.author
        keydoc = await self.fetch_key(user)
        if not world and keydoc:
            try:
                key = keydoc["key"]
                headers = self.construct_headers(key)
                endpoint = "account/"
                results = await self.call_api(endpoint, headers)
                wid = results["world"]
            except APIError as e:
                await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                                   "`{1}`".format(user, e))
                return
        else:
            wid = await self.getworldid(world)
        if not wid:
            await self.bot.say("Nom du monde invalide")
            return
        try:
            endpoint = "wvw/matches?world={0}".format(wid)
            results = await self.call_api(endpoint)
            endpoint_ = "worlds?id={0}".format(wid)
            worldinfo = await self.call_api(endpoint_)
            worldname = worldinfo["name"]
            population = worldinfo["population"]
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        worldcolor = ""
        for key, value in results["all_worlds"].items():
            if wid in value:
                worldcolor = key
        if not worldcolor:
            await self.bot.say("Impossible de résoudre la couleur du monde")
            return
        if worldcolor == "red":
            color = discord.Colour.red()
        elif worldcolor == "green":
            color = discord.Colour.green()
        else:
            color = discord.Colour.blue()
        score = results["scores"][worldcolor]
        ppt = 0
        victoryp = results["victory_points"][worldcolor]
        for m in results["maps"]:
            for objective in m["objectives"]:
                if objective["owner"].lower() == worldcolor:
                    ppt += objective["points_tick"]
        if population == "VeryHigh":
            population = "Très élevée"
        kills = results["kills"][worldcolor]
        deaths = results["deaths"][worldcolor]
        kd = round((kills / deaths), 2)
        data = discord.Embed(description="Performance", colour=color)
        data.add_field(name="Score", value=score)
        data.add_field(name="Points par tick", value=ppt)
        data.add_field(name="Points de victoire", value=victoryp)
        data.add_field(name="K/D ratio", value=str(kd), inline=False)
        data.add_field(name="Population", value=population, inline=False)
        data.set_author(name=worldname)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.command(pass_context=True)
    async def gw2wiki(self, ctx, *search):
        """Recherche dans le wiki de Guild Wars 2
        Renvoie le premier résultat, pas forcémment le bon.
        """
        if not soupAvailable:
            await self.bot.say("BeautifulSoup doit être installé "
                               "pour que cette commande fonctionne.")
            return
        search = "+".join(search)
        wiki = "https://wiki-fr.guildwars2.com/"
        wiki_ = "https://wiki-fr.guildwars2.com"
        search = search.replace(" ", "+")
        user = ctx.message.author
        url = wiki + \
            "index.php?title=Special%3ASearch&profile=default&fulltext=Search&search={0}".format(
                search)
        async with self.session.get(url) as r:
            results = await r.text()
            soup = BeautifulSoup(results, 'html.parser')
        try:
            div = soup.find("div", {"class": "mw-search-result-heading"})
            a = div.find('a')
            link = a['href']
            await self.bot.say("{0.mention}: {1}{2}".format(user, wiki_, link))
        except:
            await self.bot.say("{0.mention}, Aucun résultat trouvé".format(user))


    @commands.command(pass_context=True, aliases=["eventtimer", "eventtimers"])
    async def et(self, ctx):
        """Simple Event Timer de world boss"""
        embed = self.schedule_embed(self.get_upcoming_bosses())
        try:
            await self.bot.say(embed=embed)
        except:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")

    @commands.group(pass_context=True, aliases=["d"])
    async def daily(self, ctx):
        """Commande montrant les 'dailies'"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)


    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="pve", aliases=["e", "E", "PVE"])
    async def daily_pve(self, ctx):
        """Afficher les dailies PvE d'aujourd'hui"""
        try:
            output = await self.daily_handler("pve")
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        await self.bot.say(output)

    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="wvw", aliases=["w", "WVW", "W"])
    async def daily_wvw(self, ctx):
        """Afficher les dailies McM d'aujourd'hui"""
        try:
            output = await self.daily_handler("wvw")
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        await self.bot.say(output)

    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="pvp", aliases=["p", "P", "PVP"])
    async def daily_pvp(self, ctx):
        """Afficher les dailies PvP d'aujourd'hui"""
        try:
            output = await self.daily_handler("pvp")
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        await self.bot.say(output)

    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="fractals", aliases=["f", "F", "Fractals"])
    async def daily_fractals(self, ctx):
        """Affiche les dailies de fractales"""
        try:
            output = await self.daily_handler("fractals")
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        await self.bot.say(output)

    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="psna")
    async def daily_psna(self, ctx):
        """Afficher les sites actuels de l'agent du réseau d'approvisionnement du Pacte"""
        output = ("Collez ceci dans un message de chat "
                           "Lieux: ```{0}```".format(self.get_psna()))
        await self.bot.say(output)
        return

    @commands.cooldown(1, 10, BucketType.user)
    @daily.command(pass_context=True, name="all", aliases=["A", "a"])
    async def daily_all(self, ctx):
        """Montre tous les dailies"""
        try:
            endpoint = "achievements/daily"
            results = await self.call_api(endpoint)
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        output = await self.display_all_dailies(results)
        await self.bot.say("```markdown\n" + output + "```")

    @checks.admin_or_permissions(manage_server=True)
    @commands.cooldown(1, 5, BucketType.user)
    @daily.group(pass_context=True, name="notifier", no_pm=True)
    async def daily_notifier(self, ctx):
        """Envoie les dailies sur un canal spécifique
        Tout d'abord, spécifiez un canal en utilisant `!daily notifier channel <canak>`
        Et veillez à ce que le notifier soit allumé avec la commande `!daily notifier toggle on`
        """
        server = ctx.message.server
        serverdoc = await self.fetch_server(server)
        if not serverdoc:
            default_channel = server.default_channel.id
            serverdoc = {"_id": server.id, "on": False,
                         "canal": default_channel, "language": "fr",
                         "daily" : {"on": False, "channel": None, "autodelete": False, "last_message": None},
                         "news" : {"on": False, "channel": None}}
            await self.db.settings.insert_one(serverdoc)
        if ctx.invoked_subcommand is None or isinstance(ctx.invoked_subcommand, commands.Group):
            await self.bot.send_cmd_help(ctx)
            return


    @daily_notifier.command(pass_context=True, name="channel")
    async def daily_notifier_channel(self, ctx, channel: discord.Channel=None):
        """Définit le canal pour envoyer les quotidiens,
        si aucun n'est spécifié, le canal par défaut du serveur sera utilisé."""
        server = ctx.message.server
        if channel is None:
            channel = ctx.message.server.default_channel
        if not server.get_member(self.bot.user.id
                                 ).permissions_in(channel).send_messages:
            await self.bot.say("Je n'ai pas la permission d'envoyer des "
                               "messages à {0.mention}".format(channel))
            return
        await self.db.settings.update_one({"_id": server.id}, {"$set": {"daily.channel": channel.id}})
        channel = await self.get_daily_channel(server)
        try:
            endpoint = "achievements/daily"
            results = await self.call_api(endpoint)
        except APIError as e:
            print("Exception while sending daily notifs {0}".format(e))
            return
        example = await self.display_all_dailies(results, True)
        await self.bot.send_message(channel, "Je vais maintenant envoyer les daily "
                                    "à {0.mention}. Assurez-vous que le notifier soit bien on "
                                    "en utilisant la commande `!daily notifier toggle on.` "
                                    "Exemple:\n```markdown\n{1}```".format(channel, example))

    @daily_notifier.command(pass_context=True, name="toggle")
    async def daily_notifier_toggle(self, ctx, on_off: bool):
        """Bascule les dailies à la réinitialisation du serveur"""
        server = ctx.message.server
        if on_off is not None:
            await self.db.settings.update_one({"_id": server.id}, {"$set": {"daily.on" : on_off}})
        serverdoc = await self.fetch_server(server)
        if serverdoc["daily"]["on"]:
            await self.bot.say("Je vous informerai sur ce serveur à propos des dailies")
        else:
            await self.bot.say("Je ne vais pas envoyer de "
                               "notifications à propos des dailies")


    async def daily_handler(self, search):
        endpoint = "achievements/daily"
        results = await self.call_api(endpoint)
        data = results[search]
        dailies = []
        daily_format = []
        daily_filtered = []
        for x in data:
            if x["level"]["max"] == 80:
                dailies.append(x)
        for daily in dailies:
            d = await self.db.achievements.find_one({"_id": daily["id"]})
            daily_format.append(d)
        if search == "fractals":
            for daily in daily_format:
                if not daily["name"].startswith("Daily Tier"):
                    daily_filtered.append(daily)
                if daily["name"].startswith("Daily Tier 4"):
                    daily_filtered.append(daily)
        else:
            daily_filtered = daily_format
        output = "{0} Les daily du jours sont: ```".format(search.capitalize())
        for x in daily_filtered:
            output += "\n" + x["name"]
        output += "```"
        return output

    async def display_all_dailies(self, dailylist, tomorrow=False):
        dailies = ["#Daily PSNA:", self.get_psna()]
        if tomorrow:
            dailies[0] = "#PSNA actuellement:"
            dailies.append("#PSNA dans 8 heures:")
            dailies.append(self.get_psna(1))
        fractals = []
        sections = ["pve", "pvp", "wvw", "fractals"]
        for x in sections:
            section = dailylist[x]
            dailies.append("#{0} DAILIES:".format(x.upper()))
            if x == "fractals":
                for x in section:
                    d = await self.db.achievements.find_one({"_id": x["id"]})
                    fractals.append(d)
                for frac in fractals:
                    if not frac["name"].startswith("Daily Tier"):
                        dailies.append(frac["name"])
                    if frac["name"].startswith("Daily Tier 4"):
                        dailies.append(frac["name"])
            else:
                for x in section:
                    if x["level"]["max"] == 80:
                        d = await self.db.achievements.find_one({"_id": x["id"]})
                        dailies.append(d["name"])
        return "\n".join(dailies)

    def get_psna(self, modifier=0):
            offset = datetime.timedelta(hours=-8)
            tzone = datetime.timezone(offset)
            day = datetime.datetime.now(tzone).weekday()
            if day + modifier > 6:
                modifier = -6
            return self.gamedata["pact_supply"][day + modifier]

    @checks.admin_or_permissions(manage_server=True)
    @commands.group(pass_context=True, no_pm=True)
    async def newsfeed(self, ctx):
        """Flux de nouvelles automatique de guildwars2.com"""
        server = ctx.message.server
        serverdoc = await self.fetch_server(server)
        if not serverdoc:
            default_channel = server.default_channel.id
            serverdoc = {"_id": server.id, "on": False,
                         "channel": default_channel, "language": "fr",
                         "daily" : {"on": False, "channel": None, "autodelete": False, "last_message": None},
                         "news" : {"on": False, "channel": None}}
            await self.db.settings.insert_one(serverdoc)
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @newsfeed.command(pass_context=True, name="channel")
    async def newsfeed_channel(self, ctx, channel: discord.Channel=None):
        """Définit le canal pour envoyer les nouvelles.
        Si aucun canal n'est spécifié, le canal par défaut du serveur sera utilisé"""
        server = ctx.message.server
        if channel is None:
            channel = ctx.message.server.default_channel
        if not server.get_member(self.bot.user.id
                                 ).permissions_in(channel).send_messages:
            await self.bot.say("Je n'ai pas la permission d'envoyer des "
                               "messages à {0.mention}".format(channel))
            return
        await self.db.settings.update_one({"_id": server.id}, {"$set": {"news.channel": channel.id}})
        await self.bot.send_message(channel, "Je vais maintenant envoyer les news de guildwars2.com "
                                    "à {0.mention}. Assurez-vous que le notifier soit bien on "
                                    "en utilisant la commande `!newsfeed toggle on`. ".format(channel))

    @newsfeed.command(pass_context=True, name="toggle")
    async def newsfeed_toggle(self, ctx, on_off: bool):
        """Permet d'afficher les news"""
        server = ctx.message.server
        if on_off is not None:
            await self.db.settings.update_one({"_id": server.id}, {"$set": {"news.on" : on_off}})
        serverdoc = await self.fetch_server(server)
        if serverdoc["news"]["on"]:
            await self.bot.say("Je vais maintenant envoyer les news de guildwars2.com")
        else:
            await self.bot.say("Je ne vais pas envoyer de "
                               "notifications à propos des news")



    @commands.group(pass_context=True, no_pm=True, name="updatenotifier")
    @checks.admin_or_permissions(manage_server=True)
    async def gamebuild(self, ctx):
        """Commande lié aux nouvelles mises à jour"""
        server = ctx.message.server
        serverdoc = await self.fetch_server(server)
        if not serverdoc:
            default_channel = server.default_channel.id
            serverdoc = {"_id": server.id, "on": False,
                         "channel": default_channel, "language": "fr",
                         "daily" : {"on": False, "channel": None, "autodelete": False, "last_message": None},
                         "news" : {"on": False, "channel": None}}
            await self.db.settings.insert_one(serverdoc)
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @gamebuild.command(pass_context=True)
    async def channel(self, ctx, channel: discord.Channel=None):
        """Définit le canal pour envoyer l'annonce de mise à jour.
        Si aucun canal n'est spécifié, le canal par défaut du serveur sera utilisé"""
        server = ctx.message.server
        if channel is None:
            channel = ctx.message.server.default_channel
        if not server.get_member(self.bot.user.id
                                 ).permissions_in(channel).send_messages:
            await self.bot.say("Je n'ai pas la permission d'envoyer des "
                               "messages à {0.mention}".format(channel))
            return
        await self.db.settings.update_one({"_id": server.id}, {"$set": {"channel": channel.id}})
        channel = await self.get_announcement_channel(server)
        await self.bot.send_message(channel, "Je vais maintenant envoyer les annonces de nouvelle version "
                                    "à {0.mention}. Assurez-vous que le notifier soit bien on "
                                    "en utilisant la commande `!updatenotifier toggle on`".format(channel))

    @checks.mod_or_permissions(administrator=True)
    @gamebuild.command(pass_context=True)
    async def toggle(self, ctx, on_off: bool):
        """Permet de vérifier les nouvelles versions"""
        server = ctx.message.server
        if on_off is not None:
            await self.db.settings.update_one({"_id": server.id}, {"$set": {"on": on_off}})
        serverdoc = await self.fetch_server(server)
        if serverdoc["on"]:
            await self.bot.say("Je vous informerai sur ce serveur sur les nouvelles versions")
        else:
            await self.bot.say("Je ne vais pas envoyer "
                               "de notifications à propos des nouvelles versions")

    @commands.group(pass_context=True)
    async def tp(self, ctx):
        """Commandes liées au comptoir
        Ne nécessite pas de permissions supplémentaires"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @commands.cooldown(1, 10, BucketType.user)
    @tp.command(pass_context=True, name="current")
    async def tp_current(self, ctx, buys_sells):
        """Affiche les transactions en cours
        de vente et d'achat"""
        user = ctx.message.author
        color = self.getColor(user)
        state = buys_sells.lower()
        scopes = ["tradingpost"]
        endpoint = "commerce/transactions/current/{0}".format(state)
        keydoc = await self.fetch_key(user)
        if state == "buys" or state == "sells":
            try:
                await self._check_scopes_(user, scopes)
                key = keydoc["key"]
                headers = self.construct_headers(key)
                accountname = keydoc["account_name"]
                results = await self.call_api(endpoint, headers)
            except APIKeyError as e:
                await self.bot.say(e)
                return
            except APIBadRequest:
                await self.bot.say("Aucune transaction en cours")
                return
            except APIError as e:
                await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                                   "`{1}`".format(user, e))
                return
        else:
            await self.bot.say("{0.mention}, S'il vous plaît utilisez 'sells' ou 'buys' comme paramètre".format(user))
            return
        data = discord.Embed(description='Current ' + state, colour=color)
        data.set_author(name='Aperçu des transactions de {0}'.format(accountname))
        data.set_thumbnail(
            url="https://wiki.guildwars2.com/images/thumb/d/df/Black-Lion-Logo.png/300px-Black-Lion-Logo.png")
        data.set_footer(text="Compagnie commerciale du Lion noir")
        results = results[:20]  # Only display 20 most recent transactions
        item_id = ""
        dup_item = {}
        itemlist = []
        # Collect listed items
        for result in results:
            itemdoc = await self.fetch_item(result["item_id"])
            itemlist.append(itemdoc)
            item_id += str(result["item_id"]) + ","
            if result["item_id"] not in dup_item:
                dup_item[result["item_id"]] = len(dup_item)
        # Get information about all items, doesn't matter if string ends with ,
        endpoint_items = "items?ids={0}".format(str(item_id))
        endpoint_listing = "commerce/listings?ids={0}".format(str(item_id))
        # Call API once for all items
        try:
            listings = await self.call_api(endpoint_listing)
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                               "`{1}`".format(user, e))
            return
        for result in results:
            # Store data about transaction
            index = dup_item[result["item_id"]]
            quantity = result["quantity"]
            price = result["price"]
            item_name = itemlist[index]["name"]
            offers = listings[index][state]
            max_price = offers[0]["unit_price"]
            data.add_field(name=item_name, value=str(quantity) + " x " + self.gold_to_coins(price)
                           + " | Max. offer: " + self.gold_to_coins(max_price), inline=False)
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")


    @commands.cooldown(1, 15, BucketType.user)
    @tp.command(pass_context=True, name="price")
    async def tp_price(self, ctx, *, item: str):
        """Cherche le prix d'un item"""
        user = ctx.message.author
        color = self.getColor(user)
        choice = await self.itemname_to_id(item, user)
        if not choice:
	        return
        try:
            commerce = 'commerce/prices/'
            choiceid = str(choice["_id"])
            endpoint = commerce + choiceid
            results = await self.call_api(endpoint)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APINotFound as e:
            await self.bot.say("{0.mention}, Cet objet n'est pas dans le TP."
                               "".format(user))
            return
        except APIError as e:
            await self.bot.say("{0.mention}, L'API a répondu avec l'erreur suivante: "
                                "`{1}`".format(user, e))
            return
        buyprice = results["buys"]["unit_price"]
        sellprice = results ["sells"]["unit_price"]
        itemname = choice["name"]
        level = str(choice["level"])
        rarity = choice["rarity"]
        itemtype = self.gamedata["items"]["types"][choice["type"]].lower()
        description = "Un niveau {} {} {}".format(level, rarity.lower(), itemtype.lower())
        if buyprice != 0:
            buyprice = self.gold_to_coins(buyprice)
        if sellprice != 0:
            sellprice = self.gold_to_coins(sellprice)
        if buyprice == 0:
            buyprice = 'Pas d\'acheteurs'
        if sellprice == 0:
            sellprice = 'Pas de vendeurs'
        data = discord.Embed(title=itemname, description=description, colour=self.rarity_to_color(rarity))
        if "icon" in choice:
            data.set_thumbnail(url=choice["icon"])
        data.add_field(name="Prix d'achat", value=buyprice, inline=False)
        data.add_field(name="Prix de vente", value=sellprice, inline=False)
        data.set_footer(text=choice["chat_link"])
        try:
            await self.bot.say(embed=data)
        except discord.HTTPException:
            await self.bot.say("Problème d'intégration des données sur discord")

    async def itemname_to_id(self, item, user):
        item_sanitized = re.escape(item)
        search = re.compile(item_sanitized + ".*", re.IGNORECASE)
        cursor = self.db.items.find({"name": search})
        number = await cursor.count()
        if not number:
            await self.bot.say("Votre recherche m'a donné aucun résultat, désolé. Vérifiez les fautes de frappe.")
            return None
        if number > 20:
            await self.bot.say("Votre recherche m'a donné {0} résultats. Soyez plus précis".format(number))
            return None
        items = []
        msg = "Lequel de ces articles vous intéresse? Tapez le nombre situé à côté```"
        async for item in cursor:
            items.append(item)
        if number != 1:
            for c, m in enumerate(items):
                msg += "\n{}: {} ({})".format(c, m["name"], m["rarity"])
            msg += "```"
            message = await self.bot.say(msg)
            answer = await self.bot.wait_for_message(timeout=120, author=user)
            try:
                num = int(answer.content)
                choice = items[num]
            except:
                await self.bot.edit_message(message, "Ce n'est pas un numéro dans la liste")
                return None
            try:
                await self.bot.delete_message(message)
                await self.bot.delete_message(answer)
            except:
                pass
        else:
            choice = items[0]
        return choice


    @commands.cooldown(1, 15, BucketType.user)
    @commands.command(pass_context=True)
    async def search(self, ctx, *, item):
        """Trouve des objets dans ton compte!"""
        user = ctx.message.author
        scopes = ["inventories", "characters"]
        keydoc = await self.fetch_key(user)
        try:
            await self._check_scopes_(user, scopes)
            key = keydoc["key"]
            headers = self.construct_headers(key)
            endpoint_bank = "account/bank"
            endpoint_shared = "account/inventory"
            endpoint_char = "characters?page=0"
            endpoint_material = "account/materials"
            bank = await self.call_api(endpoint_bank, headers)
            shared = await self.call_api(endpoint_shared, headers)
            material = await self.call_api(endpoint_material, headers)
            characters = await self.call_api(endpoint_char, headers)
        except APIKeyError as e:
            await self.bot.say(e)
            return
        except APIError as e:
            await self.bot.say("{0.mention}, API has responded with the following error: "
                               "`{1}`".format(user, e))
            return
        choice = await self.itemname_to_id(item, user)
        if not choice:
            return
        output = ""
        results = {"bank" : 0, "shared" : 0, "material" : 0, "characters" : {}}
        bankresults = [item["count"] for item in bank if item != None and item["id"] == choice["_id"]]
        results["bank"] = sum(bankresults)
        sharedresults = [item["count"] for item in shared if item != None and item["id"] == choice["_id"]]
        results["shared"] = sum(sharedresults)
        materialresults = [item["count"] for item in material if item != None and item["id"] == choice["_id"]]
        results["material"] = sum(materialresults)
        for character in characters:
            results["characters"][character["name"]] = 0
            bags = [bag for bag in character["bags"] if bag != None]
            equipment = [piece for piece in character["equipment"] if piece != None]
            for bag in bags:
                inv = [item["count"] for item in bag["inventory"] if item != None and item["id"] == choice["_id"]]
                results["characters"][character["name"]] += sum(inv)
            try:
                eqresults = [1 for piece in equipment if piece["id"] == choice["_id"]]
                results["characters"][character["name"]] += sum(eqresults)
            except:
                pass
        if results["bank"]:
            output += "BANQUE: Trouvé {0}\n".format(results["bank"])
        if results["material"]:
            output += "DÉPÔT DE RESSOURCES: Trouvé {0}\n".format(results["material"])
        if results["shared"]:
            output += "PARTAGÉ: Trouvé {0}\n".format(results["shared"])
        if results["characters"]:
            for char, value in results["characters"].items():
                if value:
                    output += "{0}: Trouvé {1}\n".format(char.upper(), value)
        if not output:
            await self.bot.edit_message(message, "Désolé, je n'ai rien trouvé sur votre compte. "
                                                                        "Assurez-vous que vous avez sélectionné le "
                                                                        "bon objet")
        else:
            await self.bot.say("```" + output + "```")

    @commands.cooldown(1, 5, BucketType.user)
    @commands.command(pass_context=True)
    async def skillinfo(self, ctx, *, skill):
        """Informations sur une compétence donnée"""
        user = ctx.message.author
        skill_sanitized = re.escape(skill)
        search = re.compile(skill_sanitized + ".*", re.IGNORECASE)
        cursor = self.db.skills.find({"name": search})
        number = await cursor.count()
        if not number:
            await self.bot.say("Votre recherche m'a donné aucun résultat, désolé. Vérifiez les fautes de frappe.")
            return
        if number > 20:
            await self.bot.say("Votre recherche m'a donné {0} résultats. Soyez plus précis".format(number))
            return
        items = []
        msg = "Lequel de ces articles vous intéresse? Tapez le nombre situé à côté```"
        async for item in cursor:
            items.append(item)
        if number != 1:
            for c, m in enumerate(items):
                msg += "\n{}: {}".format(c, m["name"])
            msg += "```"
            message = await self.bot.say(msg)
            answer = await self.bot.wait_for_message(timeout=120, author=user)
            output = ""
            try:
                num = int(answer.content)
                choice = items[num]
            except:
                await self.bot.edit_message(message, "Ce n'est pas un numéro dans la liste")
                return
            try:
                await self.bot.delete_message(answer)
            except:
                pass
        else:
            message = await self.bot.say("Recherche dans l'ensemble...")
            choice = items[0]
        data = self.skill_embed(choice)
        try:
            await self.bot.edit_message(message, new_content=" ", embed=data)
        except discord.HTTPException:
            await self.bot.say("Besoin d'autorisation pour intégrer des liens")


    async def skill_embed(self, skill):
        #Very inconsistent endpoint, playing it safe
        description = None
        if "description" in skill:
            description = skill["description"]
        url = "https://wiki-fr.guildwars2.com/wiki/" + skill["name"].replace(' ', '_')
        async with self.session.head(url) as r:
            if not r.status == 200:
               url = None
        data = discord.Embed(title=skill["name"], description=description, url=url)
        if "icon" in skill:
            data.set_thumbnail(url=skill["icon"])
        if "professions" in skill:
            if skill["professions"]:
                professions = skill["professions"]
                if len(professions) != 1:
                    data.add_field(name="Professions", value=", ".join(professions))
                elif len(professions) == 9:
                    data.add_field(name="Professions", value="All")
                else:
                    data.add_field(name="Profession", value=", ".join(professions))
        if "facts" in skill:
            for fact in skill["facts"]:
                try:
                    if fact["type"] == "Recharge":
                        data.add_field(name="Cooldown", value=fact["value"])
                    if fact["type"] == "Distance" or fact["type"] == "Number":
                        data.add_field(name=fact["text"], value=fact["value"])
                    if fact["type"] == "ComboField":
                        data.add_field(name=fact["text"], value=fact["field_type"])
                except:
                    pass
        return data

    def news_embed(self, item):
        description = "[Clique Ici]({0})\n{1}".format(item["link"], item["description"])
        data = discord.Embed(title="{0}".format(item["title"]), description=description, color=0xc12d2b)
        return data



    @commands.group(pass_context=True)
    @checks.is_owner()
    async def database(self, ctx):
        """Commandes liées à la gestion de base de données"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)
            return

    @commands.command(pass_context=True)
    async def changelog(self, ctx):
        """Liste des changements récent du bot"""
        await self.bot.say(self.get_changelog())

    @database.command(pass_context=True, name="create")
    async def db_create(self, ctx):
        """Créer une nouvelle base de données
        """
        await self.rebuild_database()

    @database.command(pass_context=True, name="statistics")
    async def db_stats(self, ctx):
        """Quelques statistiques
        """
        cursor = self.db.keys.find()
        result = await cursor.count()
        await self.bot.say("{} utilisateurs enregistrés".format(result))
        cursor_servers = self.db.settings.find()
        cursor_daily = self.db.settings.find({"daily.on" : True}, modifiers={"$snapshot": True})
        cursor_news = self.db.settings.find({"news.on" : True}, modifiers={"$snapshot": True})
        result_servers = await cursor_servers.count()
        result_daily = await cursor_daily.count()
        result_news = await cursor_news.count()
        await self.bot.say("{} canal pour les notices de mise à jour\n{} canal pour les dailies "
                           "notifs\n{} canal pour les news "
                           "feed".format(result_servers, result_daily, result_news))

    @commands.command(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def prefix(self, ctx, *prefixes):
        """Définit les préfixes de bot pour ce serveur

        Accepte plusieurs préfixes séparés par un espace. Entrez deux guillemets
		si un préfixe contient des espaces.
        Exemple: prefix ! $ ? "deux mots"

        L'émission de cette commande sans paramètres permet de
		réinitialiser le préfixe le serveur
        """
        server = ctx.message.server

        if prefixes == ():
            self.bot.settings.set_server_prefixes(server, [])
            self.bot.settings.save_settings()
            current_p = ", ".join(self.bot.settings.prefixes)
            await self.bot.say("Réinitialisation des préfixes du serveur. Préfixes actuels: "
                               "`{}`".format(current_p))
            return

        prefixes = sorted(prefixes, reverse=True)
        self.bot.settings.set_server_prefixes(server, prefixes)
        self.bot.settings.save_settings()
        p = "Prefixes" if len(prefixes) > 1 else "Prefix"
        await self.bot.say("{} configuré pour ce serveur.\n"
                           "Pour revenir aux préfixes globaux, faites"
                           " `{}prefix` "
                           "".format(p, prefixes[0]))

    async def rebuild_database(self):
        # Needs a lot of cleanup, but works anyway.
        start = time.time()
        await self.db.items.drop()
        await self.db.itemstats.drop()
        await self.db.achievements.drop()
        await self.db.titles.drop()
        await self.db.recipes.drop()
        await self.db.skins.drop()
        await self.db.currencies.drop()
        await self.db.skills.drop()
        await self.bot.change_presence(game=discord.Game(name="Reconstruction du cache de l'API"),
                                       status=discord.Status.dnd)
        self.bot.building_database = True
        try:
            items = await self.call_api("items")
        except Exception as e:
            print(e)
        await self.db.items.create_index("name")
        counter = 0
        done = False
        total = len(items)
        while not done:
            percentage = (counter / total) * 100
            print("Progress: {0:.1f}%".format(percentage))
            ids = ",".join(str(x) for x in items[counter:(counter + 200)])
            if not ids:
                done = True
                print("Done with items, moving to achievements")
                break
            itemgroup = await self.call_api("items?ids={0}".format(ids))
            counter += 200
            for item in itemgroup:
                item["_id"] = item["id"]
            await self.db.items.insert_many(itemgroup)
        try:
            items = await self.call_api("achievements")
        except Exception as e:
            print(e)
        await self.db.achievements.create_index("name")
        counter = 0
        done = False
        total = len(items)
        while not done:
            percentage = (counter / total) * 100
            print("Progress: {0:.1f}%".format(percentage))
            ids = ",".join(str(x) for x in items[counter:(counter + 200)])
            if not ids:
                done = True
                print("Done with achievements, moving to itemstats")
                break
            itemgroup = await self.call_api("achievements?ids={0}".format(ids))
            counter += 200
            for item in itemgroup:
                item["_id"] = item["id"]
            await self.db.achievements.insert_many(itemgroup)
        try:
            items = await self.call_api("itemstats")
        except Exception as e:
            print(e)
        counter = 0
        done = False
        itemgroup = await self.call_api("itemstats?ids=all")
        for item in itemgroup:
            item["_id"] = item["id"]
        await self.db.itemstats.insert_many(itemgroup)
        print("Itemstats complete. Moving to titles")
        counter = 0
        done = False
        await self.db.titles.create_index("name")
        itemgroup = await self.call_api("titles?ids=all")
        for item in itemgroup:
            item["_id"] = item["id"]
        await self.db.titles.insert_many(itemgroup)
        print("Titles done!")
        try:
            items = await self.call_api("recipes")
        except Exception as e:
            print(e)
        await self.db.recipes.create_index("output_item_id")
        counter = 0
        done = False
        total = len(items)
        while not done:
            percentage = (counter / total) * 100
            print("Progress: {0:.1f}%".format(percentage))
            ids = ",".join(str(x) for x in items[counter:(counter + 200)])
            if not ids:
                done = True
                print("Done with recioes")
                break
            itemgroup = await self.call_api("recipes?ids={0}".format(ids))
            counter += 200
            for item in itemgroup:
                item["_id"] = item["id"]
            await self.db.recipes.insert_many(itemgroup)
        try:
            items = await self.call_api("skins")
        except Exception as e:
            print(e)
        await self.db.skins.create_index("name")
        counter = 0
        done = False
        total = len(items)
        while not done:
            percentage = (counter / total) * 100
            print("Progress: {0:.1f}%".format(percentage))
            ids = ",".join(str(x) for x in items[counter:(counter + 200)])
            if not ids:
                done = True
                print("Done with skins")
                break
            itemgroup = await self.call_api("skins?ids={0}".format(ids))
            counter += 200
            for item in itemgroup:
                item["_id"] = item["id"]
            await self.db.skins.insert_many(itemgroup)
        counter = 0
        done = False
        await self.db.currencies.create_index("name")
        itemgroup = await self.call_api("currencies?ids=all")
        for item in itemgroup:
            item["_id"] = item["id"]
        await self.db.currencies.insert_many(itemgroup)
        end = time.time()
        counter = 0
        done = False
        await self.db.skills.create_index("name")
        itemgroup = await self.call_api("skills?ids=all")
        for item in itemgroup:
            item["_id"] = item["id"]
        await self.db.skills.insert_many(itemgroup)
        end = time.time()
        self.bot.building_database = False
        await self.bot.change_presence(game=discord.Game(name="!help"),
                                       status=discord.Status.online)

        print("Database done! Time elapsed: {0} seconds".format(end - start))

    async def _gamebuild_checker(self):
        while self is self.bot.get_cog("GuildWars2"):
            try:
                if await self.update_build():
                    channels = await self.get_channels()
                    try:
                        link = await self.get_patchnotes()
                        patchnotes = "\nPatchnotes: " + link
                    except:
                        patchnotes = ""
                    if channels:
                        for channel in channels:
                            try:
                                await self.bot.send_message(self.bot.get_channel(channel),
                                                            "@here Guild Wars 2 vient d'être mis à jour! Nouvelle version: "
                                                            "`{0}`{1}".format(self.build["id"], patchnotes))
                            except:
                                pass
                    else:
                        print(
                            "Une nouvelle version a été trouvée, mais aucun canal à notifier n'a été trouvé. Peut-être est-ce une erreur?")
                    await self.rebuild_database()
                await asyncio.sleep(60)
            except Exception as e:
                print(
                    "Update ontifier has encountered an exception: {0}".format(e))
                await asyncio.sleep(60)
                continue


    async def news_checker(self):
        while self is self.bot.get_cog("GuildWars2"):
            try:
                to_post = await self.check_news()
                if to_post:
                    embeds = []
                    for item in to_post:
                        embeds.append(self.news_embed(item))
                    await self.send_news(embeds)
                await asyncio.sleep(300)
            except APIError as e:
                print(
                    "News ontifier has encountered an exception: {0}".format(e))
                await asyncio.sleep(300)
                continue



    async def daily_notifs(self):
        while self is self.bot.get_cog("GuildWars2"):
            try:
                if self.check_day():
                    await asyncio.sleep(300)
                    await self.send_daily_notifs()
                await asyncio.sleep(60)
            except Exception as e:
                print("Daily notifier exception: {0}\nExecution will continue".format(e))
                await asyncio.sleep(60)
                continue


    def get_changelog(self):
        with open("data/red/changelog.txt", "r") as f:
	            return f.read()


    def gold_to_coins(self, money):
        gold, remainder = divmod(money, 10000)
        silver, copper = divmod(remainder, 100)
        if not gold:
            if not silver:
                return "{0} cuivre".format(copper)
            else:
                return "{0} argent et {1} cuivre".format(silver, copper)
        else:
            return "{0} or, {1} argent et {2} cuivre".format(gold, silver, copper)

    def handle_duplicates(self, upgrades):
        formatted_list = []
        for x in upgrades:
            if upgrades.count(x) != 1:
                formatted_list.append(x + " x" + str(upgrades.count(x)))
                upgrades[:] = [i for i in upgrades if i != x]
            else:
                formatted_list.append(x)
        return formatted_list

    def construct_headers(self, key):
        headers = {"Authorization": "Bearer {0}".format(key)}
        headers.update(DEFAULT_HEADERS)
        return headers

    async def getworldid(self, world):
        if world is None:
            return None
        try:
            endpoint = "worlds?ids=all"
            results = await self.call_api(endpoint)
        except APIError:
            return None
        for w in results:
            if w["name"].lower() == world.lower():
                return w["id"]
        return None

    async def _get_guild_(self, gid):
        endpoint = "guild/{0}".format(gid)
        try:
            results = await self.call_api(endpoint)
        except APIError:
            return None
        return results

    async def _get_title_(self, tid):
        try:
            results = await self.db.titles.find_one({"_id" : tid})
            title = results["name"]
        except:
            return ""
        return title


    async def check_news(self):
        last_news = self.cache["news"]
        url = "https://www.guildwars2.com/fr/feed/"
        async with self.session.get(url) as r:
            feed = et.fromstring(await r.text())[0]
        to_post = []
        if last_news:
            for item in feed.findall("item"):
                try:
                    if item.find("title").text not in last_news:
                        to_post.append({
                        "link" : item.find("link").text,
                        "title" : item.find("title").text,
                        "description" : item.find("description").text.split("</p>", 1)[0]
                        })
                except:
                    pass
        self.cache["news"] = [x.find("title").text for x in feed.findall("item")]
        dataIO.save_json('data/guildwars2/cache.json', self.cache)
        return to_post


    async def call_api(self, endpoint, headers=DEFAULT_HEADERS):
        apiserv = 'https://api.guildwars2.com/v2/'
        url = apiserv + endpoint
        async with self.session.get(url, headers=headers) as r:
            if r.status != 200 and r.status != 206:
                if r.status == 400:
                    raise APIBadRequest("Bad request")
                if r.status == 404:
                    raise APINotFound("Not found")
                if r.status == 403:
                    raise APIForbidden("Access denied")
                if r.status == 429:
                    print (time.strftime('%a %H:%M:%S'), "Api call limit reached")
                    raise APIConnectionError(
                        "Requests limit has been achieved. Try again later.")
                else:
                    raise APIConnectionError(str(r.status))
            results = await r.json()
        return results

    def get_age(self, age):
        hours, remainder = divmod(int(age), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        if days:
            fmt = '{d} jours, {h} heures, {m} minutes, et {s} secondes'
        else:
            fmt = '{h} heures, {m} minutes, et {s} seconds'
        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    async def fetch_statname(self, item):
        statset = await self.db.itemstats.find_one({"_id": item})
        return statset["name"]

    async def fetch_item(self, item):
        return await self.db.items.find_one({"_id": item})

    def getColor(self, user):
        try:
            color = user.colour
        except:
            color = discord.Embed.Empty
        return color

    def rarity_to_color(self, rarity):
        return int(self.gamedata["items"]["rarity_colors"][rarity], 0)

    async def get_channels(self):
        try:
            channels = []
            cursor = self.db.settings.find(modifiers={"$snapshot": True})
            async for server in cursor:
                try:
                    if server["on"]:
                        channels.append(server["channel"])
                except:
                    pass
            return channels
        except:
            return None

    async def get_announcement_channel(self, server):
        try:
            serverdoc = await self.fetch_server(server)
            return server.get_channel(serverdoc["channel"])
        except:
            return None

    async def get_daily_channel(self, server):
        try:
            serverdoc = await self.fetch_server(server)
            return server.get_channel(serverdoc["daily"]["channel"])
        except:
            return None

    async def update_build(self):
        endpoint = "build"
        try:
            results = await self.call_api(endpoint)
        except APIError:
            return False
        build = results["id"]
        if not self.build["id"] == build:
            self.build["id"] = build
            dataIO.save_json('data/guildwars2/build.json', self.build)
            return True
        else:
            return False

    def generate_schedule(self):
        time = datetime.datetime(1, 1, 1)
        normal = self.gamedata["event_timers"]["bosses"]["normal"]
        hardcore = self.gamedata["event_timers"]["bosses"]["hardcore"]
        schedule = []
        counter = 0
        while counter < 12:
            for boss in normal:
                increment = datetime.timedelta(hours=boss["interval"] * counter)
                time = (datetime.datetime(1, 1, 1, *boss["start_time"]) + increment)
                if time.day != 1:
                    continue
                output = {"name" : boss["name"], "time" : str(time.time()), "waypoint" : boss["waypoint"]}
                schedule.append(output)
            counter += 1
        for boss in hardcore:
            for hours in boss["times"]:
                output = {"name" : boss["name"], "time" : str(datetime.time(*hours)), "waypoint" : boss["waypoint"]}
                schedule.append(output)
        return sorted(schedule, key=lambda t: datetime.datetime.strptime(t["time"], "%H:%M:%S").time())


    def get_upcoming_bosses(self, timezone=None): #TODO
        upcoming_bosses = []
        time = datetime.datetime.utcnow()
        counter = 0
        day = 0
        done = False
        while not done:
            for boss in self.boss_schedule:
                if counter == 8:
                    done = True
                    break
                boss_time = datetime.datetime.strptime(boss["time"], "%H:%M:%S")
                boss_time = boss_time.replace(year=time.year, month=time.month, day=time.day) + datetime.timedelta(days=day)
                if time < boss_time:
                    delta = (boss_time - time)
                    boss_time = get_datetime_timezoned(boss_time)
                    output = {"name" : boss["name"], "time" : str(boss_time.time()), "waypoint" : boss["waypoint"], "diff" : self.format_timedelta(delta)}
                    upcoming_bosses.append(output)
                    counter +=1
            day += 1
        return upcoming_bosses


    def schedule_embed(self, schedule):
        data = discord.Embed()
        for boss in schedule:
            value = "Heure: {}\nWaypoint: {}".format(boss["time"], boss["waypoint"])
            data.add_field(name="{} dans {}".format(boss["name"], boss["diff"]), value=value, inline=False)
        data.set_author(name="World boss à venir")
        data.set_footer(text="Les heures sont en GMT + 2 [Europe/Paris]")
        return data


    def format_timedelta(self, td):
        hours, remainder = divmod(td.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return "{} heures et {} minutes".format(hours, minutes)
        else:
            return "{} minutes".format(minutes)


    def check_day(self):
        current = datetime.datetime.utcnow().weekday()
        if self.cache["day"] != current:
            self.cache["day"] = current
            dataIO.save_json('data/guildwars2/cache.json', self.cache)
            return True
        else:
            return False

    async def send_daily_notifs(self):
        try:
            channels = []
            cursor = self.db.settings.find({"daily.on" : True}, modifiers={"$snapshot": True})
            async for server in cursor:
                try:
                    if "channel" in server["daily"]:
                        if server["daily"]["channel"] is not None:
                            channels.append(server["daily"]["channel"])
                except:
                    pass
            try:
                endpoint = "achievements/daily"
                results = await self.call_api(endpoint)
            except APIError as e:
                print("Exception while sending daily notifs {0}".format(e))
                return
            message = await self.display_all_dailies(results, True)
            for channel in channels:
                try:
                    await self.bot.send_message(self.bot.get_channel(channel), "```markdown\n" + message + "```\nHave a nice day!")
                except:
                    pass
        except Exception as e:
            print ("Erorr while sending daily notifs: {0}".format(e))
            return


    async def send_news(self, embeds):
        try:
            channels = []
            cursor = self.db.settings.find({"news.on" : True}, modifiers={"$snapshot": True})
            async for server in cursor:
                try:
                    if "channel" in server["news"]:
                        if server["news"]["channel"] is not None:
                            channels.append(server["news"]["channel"])
                except:
                    pass
            for chanid in channels:
                try:
                    channel = self.bot.get_channel(chanid)
                    for embed in embeds:
                        await self.bot.send_message(channel, embed=embed)
                except:
                    pass
        except Exception as e:
            print ("Erorr while sending news: {0}".format(e))
            return




    async def _check_scopes_(self, user, scopes):
        keydoc = await self.fetch_key(user)
        if not keydoc:
            raise APIKeyError(
                "Aucune clé API associée à {0.mention}. Ajoutez votre clé en utilisant la commande `!key add`.".format(user))
        if scopes:
            missing = []
            for scope in scopes:
                if scope not in keydoc["permissions"]:
                    missing.append(scope)
            if missing:
                missing = ", ".join(missing)
                raise APIKeyError(
                    "{0.mention}, missing the following scopes to use this command: `{1}`".format(user, missing))

    async def get_patchnotes(self):
        url = "https://forum-fr.guildwars2.com/forum/info/updates"
        async with self.session.get(url) as r:
            results = await r.text()
        soup = BeautifulSoup(results, 'html.parser')
        post = soup.find(class_="arenanet topic")
        return "https://forum-fr.guildwars2.com" + post.find("a")["href"]

    async def fetch_key(self, user):
        return await self.db.keys.find_one({"_id": user.id})

    async def fetch_server(self, server):
        return await self.db.settings.find_one({"_id": server.id})


def check_folders():
    if not os.path.exists("data/guildwars2"):
        print("Creating data/guildwars2")
        os.makedirs("data/guildwars2")





def check_files():
    files = {
        "gamedata.json": {},
        "build.json": {"id": None},
        "cache.json": {"day": datetime.datetime.utcnow().weekday(), "news" : []}
    }

    for filename, value in files.items():
        if not os.path.isfile("data/guildwars2/{}".format(filename)):
            print("Creating empty {}".format(filename))
            dataIO.save_json("data/guildwars2/{}".format(filename), value)


def setup(bot):
    check_folders()
    check_files()
    n = GuildWars2(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n._gamebuild_checker())
    loop.create_task(n.daily_notifs())
    loop.create_task(n.news_checker())
    bot.add_cog(n)

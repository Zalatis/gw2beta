import discord
from .utils import checks
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from __main__ import send_cmd_help
import os
import asyncio

class BotStats:
    "Vous pouvez afficher vos statistiques de bot dans le statut..."
    
    def __init__(self, bot):
        self.bot = bot
        self.derp = "data/botstats/json.json"
        self.imagenius = dataIO.load_json(self.derp)

    @checks.is_owner()
    @commands.group(pass_context=True)
    async def botstats(self, ctx):
        """Afficher les statistiques du bot dans le statut (10s update)"""

        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)
    
    @checks.is_owner()
    @botstats.command(pass_context=True)
    async def toggle(self, ctx):
        """Activer/désactiver BotStatus"""
        
        servers = str(len(self.bot.servers))
        users = str(len(set(self.bot.get_all_members())))
        if self.imagenius["TOGGLE"] is False:
            self.imagenius["TOGGLE"] = True
            self.imagenius["MAINPREFIX"] = ctx.prefix
            dataIO.save_json(self.derp, self.imagenius)
            prefix = self.imagenius["MAINPREFIX"]
            await self.bot.say("BotStats actif")
            await self.botstatz()
        else:
            self.imagenius["TOGGLE"] = False
            prefix = self.imagenius["MAINPREFIX"]
            dataIO.save_json(self.derp, self.imagenius)
            await self.bot.say("BotStats inactif")
            await self.botstatz()

    @checks.is_owner()
    @botstats.command(pass_context=True)
    async def message(self, ctx, *, message):
        """You can set the way your botstats is set!


        {0} = Prefix du bot
        {1} = Serveurs
        {2} = Total utilisateurs

        Message par défaut: {0}help | {1} serveurs | {2} utilisateurs
        """

        prefix = self.imagenius["MAINPREFIX"]
        if self.imagenius["TOGGLE"] is True:
            await self.bot.say("Avant de changer le message, éteignez votre bot! `{}botstats toggle`".format(prefix))
        else:
            self.imagenius["MESSAGE"] = message
            dataIO.save_json(self.derp, self.imagenius)
            await self.bot.say("Félicitations, vous avez réglé votre message sur ```{}```".format(message))


    @checks.is_owner()
    @botstats.command(pass_context=True)
    async def timeout(self, ctx, seconds : int):
        """Délai de mise à jour


        Par défaut 15 secondes
        """

        if seconds >= 15:
            self.imagenius["SECONDS2LIVE"] = seconds
            dataIO.save_json(self.derp, self.imagenius)
            await self.bot.say("Votre statut de bot va maintenant mettre à jour toutes les {} secondes! #BOSS".format(seconds))
        else:
            await self.bot.say("NON, NE PEUT PAS ÊTRE INFÉRIEUR À 15 SECONDES....")

    async def botstatz(self):    
        while True:
            if self.imagenius["TOGGLE"] is True:
                status = self.get_status()
                servers = str(len(self.bot.servers))
                users = str(len(set(self.bot.get_all_members())))
                botstatus = self.imagenius["MESSAGE"]
                prefix = self.imagenius["MAINPREFIX"]
                message = botstatus.format(prefix, servers, users)
                game = discord.Game(name=message)
                await self.bot.change_presence(game=game, status=status)
                await asyncio.sleep(self.imagenius["SECONDS2LIVE"])
            else:
                await self.bot.change_presence(status=None, game=None)
                return
        else:
            pass
    
    async def on_ready(self):
        if self.imagenius["TOGGLE"] is True:
            while True:
                status = self.get_status()
                servers = str(len(self.bot.servers))
                users = str(len(set(self.bot.get_all_members())))
                botstatus = self.imagenius["MESSAGE"]
                prefix = self.imagenius["MAINPREFIX"]
                message = botstatus.format(prefix, servers, users)
                game = discord.Game(name=message)
                await self.bot.change_presence(game=game, status=status)
                await asyncio.sleep(self.imagenius["SECONDS2LIVE"])
            else:
                pass
        else:
            pass
    
    def get_status(self):
        typesofstatus = {
            "idle" : discord.Status.idle,
            "dnd" : discord.Status.dnd,
            "online" : discord.Status.online, 
            "invisible" : discord.Status.invisible
        }
        for server in self.bot.servers:
            member = server.me
            break
        status = member.status
        status = typesofstatus.get(str(status))
        return status
        


def check_folders():
    if not os.path.exists("data/botstats"):
        print("Creating the botstats folder, so be patient...")
        os.makedirs("data/botstats")
        print("Finish!")

def check_files():
    twentysix = "data/botstats/json.json"
    json = {
        "MAINPREFIX" : "Ceci peut être défini lors du démarrage de botstats via [p]botstats toggle",
        "TOGGLE" : False,
        "SECONDS2LIVE" : 15,
        "MESSAGE" : "{0}help | {1} serveurs | {2} utilisateurs"
    }

    if not dataIO.is_valid_json(twentysix):
        print("Derp Derp Derp...")
        dataIO.save_json(twentysix, json)
        print("Created json.json!")

def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(BotStats(bot))

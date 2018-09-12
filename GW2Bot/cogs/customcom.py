from discord.ext import commands
from .utils.dataIO import dataIO
from .utils import checks
from .utils.chat_formatting import pagify, box
import os
import re


class CustomCommands:
    """Commandes custom

    Créer commande pour afficher du texte"""

    def __init__(self, bot):
        self.bot = bot
        self.file_path = "data/customcom/commands.json"
        self.c_commands = dataIO.load_json(self.file_path)

    @commands.group(aliases=["cc"], pass_context=True, no_pm=True)
    async def customcom(self, ctx):
        """Manager des commandes custom"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @customcom.command(name="add", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def cc_add(self, ctx, command : str, *, text):
        """Ajouter une commande

        Exemple:
        !customcom add votrecommande Le texte que vous voulez

        Arguments supplémentaires:
        https://twentysix26.github.io/Red-Docs/red_guide_command_args/
        """
        server = ctx.message.server
        command = command.lower()
        if command in self.bot.commands:
            await self.bot.say("Cette commande éxiste déjà.")
            return
        if server.id not in self.c_commands:
            self.c_commands[server.id] = {}
        cmdlist = self.c_commands[server.id]
        if command not in cmdlist:
            cmdlist[command] = text
            self.c_commands[server.id] = cmdlist
            dataIO.save_json(self.file_path, self.c_commands)
            await self.bot.say("La commande a été créé.")
        else:
            await self.bot.say("Cette commande existe déjà. Utilisez "
                               "`{}customcom edit` pour l'éditer."
                               "".format(ctx.prefix))

    @customcom.command(name="edit", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def cc_edit(self, ctx, command : str, *, text):
        """Editer une commande custom

        Exemple:
        !customcom edit votrecommande Le texte que vous voulez
        """
        server = ctx.message.server
        command = command.lower()
        if server.id in self.c_commands:
            cmdlist = self.c_commands[server.id]
            if command in cmdlist:
                cmdlist[command] = text
                self.c_commands[server.id] = cmdlist
                dataIO.save_json(self.file_path, self.c_commands)
                await self.bot.say("La commande a été édité.")
            else:
                await self.bot.say("Cette commande n'existe pas. Utilisez "
                                   "`{}customcom add` pour la créer."
                                   "".format(ctx.prefix))
        else:
            await self.bot.say("Il n'y a pas de commandes custom sur ce serveur."
                               " Utilisez `{}customcom add` pour commencer à en."
                               " créer une".format(ctx.prefix))

    @customcom.command(name="delete", pass_context=True)
    @checks.mod_or_permissions(administrator=True)
    async def cc_delete(self, ctx, command : str):
        """Supprimer une commande custom

        Exemple:
        !customcom delete votrecommande"""
        server = ctx.message.server
        command = command.lower()
        if server.id in self.c_commands:
            cmdlist = self.c_commands[server.id]
            if command in cmdlist:
                cmdlist.pop(command, None)
                self.c_commands[server.id] = cmdlist
                dataIO.save_json(self.file_path, self.c_commands)
                await self.bot.say("La commande a été supprimé.")
            else:
                await self.bot.say("Cette commande n'existe pas.")
        else:
            await self.bot.say("Il n'y a pas de commandes custom sur ce serveur."
                               " Utilisez `{}customcom add` pour commencer à en."
                               " créer une".format(ctx.prefix))

    @customcom.command(name="list", pass_context=True)
    async def cc_list(self, ctx):
        """Montre la liste des commandes custom"""
        server = ctx.message.server
        commands = self.c_commands.get(server.id, {})

        if not commands:
            await self.bot.say("Il n'y a pas de commandes custom sur ce serveur."
                               " Utilisez `{}customcom add` pour commencer à en."
                               " créer une".format(ctx.prefix))
            return

        commands = ", ".join([ctx.prefix + c for c in sorted(commands)])
        commands = "Commandes custom:\n\n" + commands

        if len(commands) < 1500:
            await self.bot.say(box(commands))
        else:
            for page in pagify(commands, delims=[" ", "\n"]):
                await self.bot.whisper(box(page))

    async def on_message(self, message):
        if len(message.content) < 2 or message.channel.is_private:
            return

        server = message.server
        prefix = self.get_prefix(message)

        if not prefix:
            return

        if server.id in self.c_commands and self.bot.user_allowed(message):
            cmdlist = self.c_commands[server.id]
            cmd = message.content[len(prefix):]
            if cmd in cmdlist:
                cmd = cmdlist[cmd]
                cmd = self.format_cc(cmd, message)
                await self.bot.send_message(message.channel, cmd)
            elif cmd.lower() in cmdlist:
                cmd = cmdlist[cmd.lower()]
                cmd = self.format_cc(cmd, message)
                await self.bot.send_message(message.channel, cmd)

    def get_prefix(self, message):
        for p in self.bot.settings.get_prefixes(message.server):
            if message.content.startswith(p):
                return p
        return False

    def format_cc(self, command, message):
        results = re.findall("\{([^}]+)\}", command)
        for result in results:
            param = self.transform_parameter(result, message)
            command = command.replace("{" + result + "}", param)
        return command

    def transform_parameter(self, result, message):
        """
        Pour des raisons de sécurités seulement les données ci-dessous
        sont traités
        """
        raw_result = "{" + result + "}"
        objects = {
            "message" : message,
            "author"  : message.author,
            "channel" : message.channel,
            "server"  : message.server
        }
        if result in objects:
            return str(objects[result])
        try:
            first, second = result.split(".")
        except ValueError:
            return raw_result
        if first in objects and not second.startswith("_"):
            first = objects[first]
        else:
            return raw_result
        return str(getattr(first, second, raw_result))


def check_folders():
    if not os.path.exists("data/customcom"):
        print("Creating data/customcom folder...")
        os.makedirs("data/customcom")


def check_files():
    f = "data/customcom/commands.json"
    if not dataIO.is_valid_json(f):
        print("Creating empty commands.json...")
        dataIO.save_json(f, {})


def setup(bot):
    check_folders()
    check_files()
    bot.add_cog(CustomCommands(bot))

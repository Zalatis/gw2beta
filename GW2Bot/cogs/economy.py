import discord
from discord.ext import commands
from cogs.utils.dataIO import dataIO
from collections import namedtuple, defaultdict, deque
from datetime import datetime
from copy import deepcopy
from .utils import checks
from cogs.utils.chat_formatting import pagify, box
from enum import Enum
from __main__ import send_cmd_help
import os
import time
import logging
import random

default_settings = {"PAYDAY_TIME": 300, "PAYDAY_CREDITS": 120,
                    "SLOT_MIN": 5, "SLOT_MAX": 100, "SLOT_TIME": 0,
                    "REGISTER_CREDITS": 0}


class EconomyError(Exception):
    pass


class OnCooldown(EconomyError):
    pass


class InvalidBid(EconomyError):
    pass


class BankError(Exception):
    pass


class AccountAlreadyExists(BankError):
    pass


class NoAccount(BankError):
    pass


class InsufficientBalance(BankError):
    pass


class NegativeValue(BankError):
    pass


class SameSenderAndReceiver(BankError):
    pass


NUM_ENC = "\N{COMBINING ENCLOSING KEYCAP}"


class SMReel(Enum):
    cherries  = "\N{CHERRIES}"
    cookie    = "\N{COOKIE}"
    two       = "\N{DIGIT TWO}" + NUM_ENC
    flc       = "\N{FOUR LEAF CLOVER}"
    cyclone   = "\N{CYCLONE}"
    sunflower = "\N{SUNFLOWER}"
    six       = "\N{DIGIT SIX}" + NUM_ENC
    mushroom  = "\N{MUSHROOM}"
    heart     = "\N{HEAVY BLACK HEART}"
    snowflake = "\N{SNOWFLAKE}"

PAYOUTS = {
    (SMReel.two, SMReel.two, SMReel.six) : {
        "payout" : lambda x: x * 2500 + x,
        "phrase" : "JACKPOT!  226! Votre mise a été multipliée x2500!"
    },
    (SMReel.flc, SMReel.flc, SMReel.flc) : {
        "payout" : lambda x: x + 1000,
        "phrase" : "Trèfles à quatre feuilles! +1000!"
    },
    (SMReel.cherries, SMReel.cherries, SMReel.cherries) : {
        "payout" : lambda x: x + 800,
        "phrase" : "Trois cerises! +800!"
    },
    (SMReel.two, SMReel.six) : {
        "payout" : lambda x: x * 4 + x,
        "phrase" : "2 6! Votre mise a été multipliée x4!"
    },
    (SMReel.cherries, SMReel.cherries) : {
        "payout" : lambda x: x * 3 + x,
        "phrase" : "Deux cerises! Votre mise a été multipliée x3!"
    },
    "3 symbols" : {
        "payout" : lambda x: x + 500,
        "phrase" : "Trois symboles! +500!"
    },
    "2 symbols" : {
        "payout" : lambda x: x * 2 + x,
        "phrase" : "Deux symboles consécutifs! Votre mise a été multipliée x2!"
    },
}

SLOT_PAYOUTS_MSG = ("Machine à sous, grille des gains:\n"
                    "{two.value} {two.value} {six.value} Mise x2500\n"
                    "{flc.value} {flc.value} {flc.value} +1000\n"
                    "{cherries.value} {cherries.value} {cherries.value} +800\n"
                    "{two.value} {six.value} Mise x4\n"
                    "{cherries.value} {cherries.value} Mise x3\n\n"
                    "Trois symboles: +500\n"
                    "Deux symboles consécutifs: Mise x2".format(**SMReel.__dict__))


class Bank:

    def __init__(self, bot, file_path):
        self.accounts = dataIO.load_json(file_path)
        self.bot = bot

    def create_account(self, user, *, initial_balance=0):
        server = user.server
        if not self.account_exists(user):
            if server.id not in self.accounts:
                self.accounts[server.id] = {}
            if user.id in self.accounts:  # Legacy account
                balance = self.accounts[user.id]["balance"]
            else:
                balance = initial_balance
            timestamp = datetime.utcnow().strftime("%d-%m-%Y %H:%M:%S")
            account = {"name": user.name,
                       "balance": balance,
                       "created_at": timestamp
                       }
            self.accounts[server.id][user.id] = account
            self._save_bank()
            return self.get_account(user)
        else:
            raise AccountAlreadyExists()

    def account_exists(self, user):
        try:
            self._get_account(user)
        except NoAccount:
            return False
        return True

    def withdraw_credits(self, user, amount):
        server = user.server

        if amount < 0:
            raise NegativeValue()

        account = self._get_account(user)
        if account["balance"] >= amount:
            account["balance"] -= amount
            self.accounts[server.id][user.id] = account
            self._save_bank()
        else:
            raise InsufficientBalance()

    def deposit_credits(self, user, amount):
        server = user.server
        if amount < 0:
            raise NegativeValue()
        account = self._get_account(user)
        account["balance"] += amount
        self.accounts[server.id][user.id] = account
        self._save_bank()

    def set_credits(self, user, amount):
        server = user.server
        if amount < 0:
            raise NegativeValue()
        account = self._get_account(user)
        account["balance"] = amount
        self.accounts[server.id][user.id] = account
        self._save_bank()

    def transfer_credits(self, sender, receiver, amount):
        if amount < 0:
            raise NegativeValue()
        if sender is receiver:
            raise SameSenderAndReceiver()
        if self.account_exists(sender) and self.account_exists(receiver):
            sender_acc = self._get_account(sender)
            if sender_acc["balance"] < amount:
                raise InsufficientBalance()
            self.withdraw_credits(sender, amount)
            self.deposit_credits(receiver, amount)
        else:
            raise NoAccount()

    def can_spend(self, user, amount):
        account = self._get_account(user)
        if account["balance"] >= amount:
            return True
        else:
            return False

    def wipe_bank(self, server):
        self.accounts[server.id] = {}
        self._save_bank()

    def get_server_accounts(self, server):
        if server.id in self.accounts:
            raw_server_accounts = deepcopy(self.accounts[server.id])
            accounts = []
            for k, v in raw_server_accounts.items():
                v["id"] = k
                v["server"] = server
                acc = self._create_account_obj(v)
                accounts.append(acc)
            return accounts
        else:
            return []

    def get_all_accounts(self):
        accounts = []
        for server_id, v in self.accounts.items():
            server = self.bot.get_server(server_id)
            if server is None:
                # Servers that have since been left will be ignored
                # Same for users_id from the old bank format
                continue
            raw_server_accounts = deepcopy(self.accounts[server.id])
            for k, v in raw_server_accounts.items():
                v["id"] = k
                v["server"] = server
                acc = self._create_account_obj(v)
                accounts.append(acc)
        return accounts

    def get_balance(self, user):
        account = self._get_account(user)
        return account["balance"]

    def get_account(self, user):
        acc = self._get_account(user)
        acc["id"] = user.id
        acc["server"] = user.server
        return self._create_account_obj(acc)

    def _create_account_obj(self, account):
        account["member"] = account["server"].get_member(account["id"])
        account["created_at"] = datetime.strptime(account["created_at"],
                                                  "%d-%m-%Y %H:%M:%S")
        Account = namedtuple("Account", "id name balance "
                             "created_at server member")
        return Account(**account)

    def _save_bank(self):
        dataIO.save_json("data/economy/bank.json", self.accounts)

    def _get_account(self, user):
        server = user.server
        try:
            return deepcopy(self.accounts[server.id][user.id])
        except KeyError:
            raise NoAccount()


class SetParser:
    def __init__(self, argument):
        allowed = ("+", "-")
        if argument and argument[0] in allowed:
            try:
                self.sum = int(argument)
            except:
                raise
            if self.sum < 0:
                self.operation = "withdraw"
            elif self.sum > 0:
                self.operation = "deposit"
            else:
                raise
            self.sum = abs(self.sum)
        elif argument.isdigit():
            self.sum = int(argument)
            self.operation = "set"
        else:
            raise


class Economy:
    """Economy

    Soyez riche et amusez-vous avec de l'argent imaginaire!"""

    def __init__(self, bot):
        global default_settings
        self.bot = bot
        self.bank = Bank(bot, "data/economy/bank.json")
        self.file_path = "data/economy/settings.json"
        self.settings = dataIO.load_json(self.file_path)
        if "PAYDAY_TIME" in self.settings:  # old format
            default_settings = self.settings
            self.settings = {}
        self.settings = defaultdict(default_settings.copy, self.settings)
        self.payday_register = defaultdict(dict)
        self.slot_register = defaultdict(dict)

    @commands.group(name="bank", pass_context=True)
    async def _bank(self, ctx):
        """Opérations de banque"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @_bank.command(pass_context=True, no_pm=True)
    async def register(self, ctx):
        """Ouvrez un compte bancaire"""
        settings = self.settings[ctx.message.server.id]
        author = ctx.message.author
        credits = 0
        if ctx.message.server.id in self.settings:
            credits = settings.get("REGISTER_CREDITS", 0)
        try:
            account = self.bank.create_account(author, initial_balance=credits)
            await self.bot.say("{} Compte créer. Balance actuelle: {}"
                               "".format(author.mention, account.balance))
        except AccountAlreadyExists:
            await self.bot.say("{} Vous avez déjà un compte "
                               " bancaire.".format(author.mention))

    @_bank.command(pass_context=True)
    async def balance(self, ctx, user: discord.Member=None):
        """Montre la montant un banque d'un utilisateur.

        Par défaut: le votre."""
        if not user:
            user = ctx.message.author
            try:
                await self.bot.say("{} vous avez: {} en banque".format(
                    user.mention, self.bank.get_balance(user)))
            except NoAccount:
                await self.bot.say("{} Vous n'avez pas de compte "
                                   " bancaire tapez `{}bank register`"
                                   " pour en ouvrir un.".format(user.mention,
                                                          ctx.prefix))
        else:
            try:
                await self.bot.say("{} a {} sur son compte bancaire".format(
                    user.name, self.bank.get_balance(user)))
            except NoAccount:
                await self.bot.say("Cet utilisateur n'a pas de compte bancaire.")

    @_bank.command(pass_context=True)
    async def transfer(self, ctx, user: discord.Member, sum: int):
        """Transfère de l'argent à un autre utilisateur"""
        author = ctx.message.author
        try:
            self.bank.transfer_credits(author, user, sum)
            logger.info("{}({}) a transféré {}$ à {}({})".format(
                author.name, author.id, sum, user.name, user.id))
            await self.bot.say("{}$ ont été transféré à {}".format(sum, user.name))
        except NegativeValue:
            await self.bot.say("Vous devez envoyé au moins 1$.")
        except SameSenderAndReceiver:
            await self.bot.say("Vous ne pouvez pas vous donner de l'argent.")
        except InsufficientBalance:
            await self.bot.say("Vous n'avez pas autant d'argent.")
        except NoAccount:
            await self.bot.say("Cet utilisateur n'a pas de compte bancaire.")

    @_bank.command(name="set", pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def _set(self, ctx, user: discord.Member, credits: SetParser):
        """Opérations bancaire administratives

        Exemples:
            !bank set @Zalati 26 - Son compte est désormais de 26$
            !bank set @Zalati +2 - Ajoute 2$
            !bank set @Zalati -6 - Reitre 6$"""
        author = ctx.message.author
        try:
            if credits.operation == "deposit":
                self.bank.deposit_credits(user, credits.sum)
                logger.info("{}({}) added {} credits to {} ({})".format(
                    author.name, author.id, credits.sum, user.name, user.id))
                await self.bot.say("{}$ ont été ajouté à {}"
                                   "".format(credits.sum, user.name))
            elif credits.operation == "withdraw":
                self.bank.withdraw_credits(user, credits.sum)
                logger.info("{}({}) removed {} credits to {} ({})".format(
                    author.name, author.id, credits.sum, user.name, user.id))
                await self.bot.say("{}$ ont été retiré à {}"
                                   "".format(credits.sum, user.name))
            elif credits.operation == "set":
                self.bank.set_credits(user, credits.sum)
                logger.info("{}({}) set {} credits to {} ({})"
                            "".format(author.name, author.id, credits.sum,
                                      user.name, user.id))
                await self.bot.say("{}$ pour le compte de {}".format(
                    user.name, credits.sum))
        except InsufficientBalance:
            await self.bot.say("L'utilisateur n'a pas assez d'argent.")
        except NoAccount:
            await self.bot.say("L'utilisateur n'a pas de compte bancaire.")

    @_bank.command(pass_context=True, no_pm=True)
    @checks.serverowner_or_permissions(administrator=True)
    async def reset(self, ctx, confirmation: bool=False):
        """Supprime tous les comptes bancaire sur ce serveur"""
        if confirmation is False:
            await self.bot.say("Cela va supprimer tous les comptes "
                               "bancaire sur ce serveur.\nSi vous en êtes"
                               "sûr tapez {}bank reset yes".format(ctx.prefix))
        else:
            self.bank.wipe_bank(ctx.message.server)
            await self.bot.say("Tous les comptes bancaire de ce serveur ont "
                               "été supprimer.")

    @commands.command(pass_context=True, no_pm=True)
    async def payday(self, ctx):  # TODO
        """Obtenez un peu d'argent sans rien faire"""
        author = ctx.message.author
        server = author.server
        id = author.id
        if self.bank.account_exists(author):
            if id in self.payday_register[server.id]:
                seconds = abs(self.payday_register[server.id][
                              id] - int(time.perf_counter()))
                if seconds >= self.settings[server.id]["PAYDAY_TIME"]:
                    self.bank.deposit_credits(author, self.settings[
                                              server.id]["PAYDAY_CREDITS"])
                    self.payday_register[server.id][
                        id] = int(time.perf_counter())
                    await self.bot.say(
                        "{} Prenez un peu d'argent, Enjoy! (+{}"
                        " $!)".format(
                            author.mention,
                            str(self.settings[server.id]["PAYDAY_CREDITS"])))
                else:
                    dtime = self.display_time(
                        self.settings[server.id]["PAYDAY_TIME"] - seconds)
                    await self.bot.say(
                        "{} Trop tôt. Pour la prochaine paie vous devez"
                        " attendre {}.".format(author.mention, dtime))
            else:
                self.payday_register[server.id][id] = int(time.perf_counter())
                self.bank.deposit_credits(author, self.settings[
                                          server.id]["PAYDAY_CREDITS"])
                await self.bot.say(
                    "{} Prenez un peu d'argent, Enjoy! (+{}$!)".format(
                        author.mention,
                        str(self.settings[server.id]["PAYDAY_CREDITS"])))
        else:
            await self.bot.say("{} Vous avez besoin d'un compte pour recevoir de l'argent."
                               " Tapez `{}bank register` pour en ouvrir un.".format(
                                   author.mention, ctx.prefix))

    @commands.group(pass_context=True)
    async def leaderboard(self, ctx):
        """Classement Serveur/global

        Par défaut : Serveur"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self._server_leaderboard)

    @leaderboard.command(name="server", pass_context=True)
    async def _server_leaderboard(self, ctx, top: int=10):
        """Montre le classement du serveur

        Par défaut le top 10"""
        # Originally coded by Airenkun - edited by irdumb
        server = ctx.message.server
        if top < 1:
            top = 10
        bank_sorted = sorted(self.bank.get_server_accounts(server),
                             key=lambda x: x.balance, reverse=True)
        bank_sorted = [a for a in bank_sorted if a.member] #  exclude users who left
        if len(bank_sorted) < top:
            top = len(bank_sorted)
        topten = bank_sorted[:top]
        highscore = ""
        place = 1
        for acc in topten:
            highscore += str(place).ljust(len(str(top)) + 1)
            highscore += (str(acc.member.display_name) + " ").ljust(23 - len(str(acc.balance)))
            highscore += str(acc.balance) + "\n"
            place += 1
        if highscore != "":
            for page in pagify(highscore, shorten_by=12):
                await self.bot.say(box(page, lang="py"))
        else:
            await self.bot.say("Pas de comptes bancaire trouvé.")

    @leaderboard.command(name="global")
    async def _global_leaderboard(self, top: int=10):
        """Montre le classement global

        Par défaut le top 10"""
        if top < 1:
            top = 10
        bank_sorted = sorted(self.bank.get_all_accounts(),
                             key=lambda x: x.balance, reverse=True)
        bank_sorted = [a for a in bank_sorted if a.member] #  exclude users who left
        unique_accounts = []
        for acc in bank_sorted:
            if not self.already_in_list(unique_accounts, acc):
                unique_accounts.append(acc)
        if len(unique_accounts) < top:
            top = len(unique_accounts)
        topten = unique_accounts[:top]
        highscore = ""
        place = 1
        for acc in topten:
            highscore += str(place).ljust(len(str(top)) + 1)
            highscore += ("{} |{}| ".format(acc.member, acc.server)
                          ).ljust(23 - len(str(acc.balance)))
            highscore += str(acc.balance) + "\n"
            place += 1
        if highscore != "":
            for page in pagify(highscore, shorten_by=12):
                await self.bot.say(box(page, lang="py"))
        else:
            await self.bot.say("Pas de comptes bancaire trouvé.")

    def already_in_list(self, accounts, user):
        for acc in accounts:
            if user.id == acc.id:
                return True
        return False

    @commands.command()
    async def payouts(self):
        """Montre les gains pour les machines à sous"""
        await self.bot.whisper(SLOT_PAYOUTS_MSG)

    @commands.command(pass_context=True, no_pm=True)
    async def slot(self, ctx, bid: int):
        """Joue à la machine à sous"""
        author = ctx.message.author
        server = author.server
        settings = self.settings[server.id]
        valid_bid = settings["SLOT_MIN"] <= bid and bid <= settings["SLOT_MAX"]
        slot_time = settings["SLOT_TIME"]
        last_slot = self.slot_register.get(author.id)
        now = datetime.utcnow()
        try:
            if last_slot:
                if (now - last_slot).seconds < slot_time:
                    raise OnCooldown()
            if not valid_bid:
                raise InvalidBid()
            if not self.bank.can_spend(author, bid):
                raise InsufficientBalance
            await self.slot_machine(author, bid)
        except NoAccount:
            await self.bot.say("{} Vous avez besoin d'un compte pour utiliser "
                               "les machines à sous. Tapez "
                               "`{}bank register` pour en ouvrir un.".format(author.mention, ctx.prefix))
        except InsufficientBalance:
            await self.bot.say("{} Vous avez besoin d'un compte avec assez "
                               "d'argent pour pouvoir jouer aux machines à sous.".format(author.mention))
        except OnCooldown:
            await self.bot.say("Laissez la machine à sous se refroidir un peu.\n"
                               "Attendez {} secondes avant de jouer".format(slot_time))
        except InvalidBid:
            await self.bot.say("Votre mise doit être comprise entre {} et {}."
                               "".format(settings["SLOT_MIN"],
                                         settings["SLOT_MAX"]))

    async def slot_machine(self, author, bid):
        default_reel = deque(SMReel)
        reels = []
        self.slot_register[author.id] = datetime.utcnow()
        for i in range(3):
            default_reel.rotate(random.randint(-999, 999)) # weeeeee
            new_reel = deque(default_reel, maxlen=3) # we need only 3 symbols
            reels.append(new_reel)                   # for each reel
        rows = ((reels[0][0], reels[1][0], reels[2][0]),
                (reels[0][1], reels[1][1], reels[2][1]),
                (reels[0][2], reels[1][2], reels[2][2]))

        slot = "~~\n~~" # Mobile friendly
        for i, row in enumerate(rows): # Let's build the slot to show
            sign = "  "
            if i == 1:
                sign = ">"
            slot += "{}{} {} {}\n".format(sign, *[c.value for c in row])

        payout = PAYOUTS.get(rows[1])
        if not payout:
            # Checks for two-consecutive-symbols special rewards
            payout = PAYOUTS.get((rows[1][0], rows[1][1]),
                     PAYOUTS.get((rows[1][1], rows[1][2]))
                                )
        if not payout:
            # Still nothing. Let's check for 3 generic same symbols
            # or 2 consecutive symbols
            has_three = rows[1][0] == rows[1][1] == rows[1][2]
            has_two = (rows[1][0] == rows[1][1]) or (rows[1][1] == rows[1][2])
            if has_three:
                payout = PAYOUTS["3 symbols"]
            elif has_two:
                payout = PAYOUTS["2 symbols"]

        if payout:
            then = self.bank.get_balance(author)
            pay = payout["payout"](bid)
            now = then - bid + pay
            self.bank.set_credits(author, now)
            await self.bot.say("{}\n{} {}\n\nVotre mise: {}\n{} → {}!"
                               "".format(slot, author.mention,
                                         payout["phrase"], bid, then, now))
        else:
            then = self.bank.get_balance(author)
            self.bank.withdraw_credits(author, bid)
            now = then - bid
            await self.bot.say("{}\n{} Rien !\nVotre mise: {}\n{} → {}!"
                               "".format(slot, author.mention, bid, then, now))

    @commands.group(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_server=True)
    async def economyset(self, ctx):
        """Paramètres economy"""
        server = ctx.message.server
        settings = self.settings[server.id]
        if ctx.invoked_subcommand is None:
            msg = "```"
            for k, v in settings.items():
                msg += "{}: {}\n".format(k, v)
            msg += "```"
            await send_cmd_help(ctx)
            await self.bot.say(msg)

    @economyset.command(pass_context=True)
    async def slotmin(self, ctx, bid: int):
        """Modifier la mise minimum"""
        server = ctx.message.server
        self.settings[server.id]["SLOT_MIN"] = bid
        await self.bot.say("La mise minimum est désormais de {}$.".format(bid))
        dataIO.save_json(self.file_path, self.settings)

    @economyset.command(pass_context=True)
    async def slotmax(self, ctx, bid: int):
        """Modifier la mise maximum"""
        server = ctx.message.server
        self.settings[server.id]["SLOT_MAX"] = bid
        await self.bot.say("La mise maximum est désormais de {}$.".format(bid))
        dataIO.save_json(self.file_path, self.settings)

    @economyset.command(pass_context=True)
    async def slottime(self, ctx, seconds: int):
        """Modifier le temps entre chaque utilisation de slot"""
        server = ctx.message.server
        self.settings[server.id]["SLOT_TIME"] = seconds
        await self.bot.say("Le délai est désormais de {} secondse.".format(seconds))
        dataIO.save_json(self.file_path, self.settings)

    @economyset.command(pass_context=True)
    async def paydaytime(self, ctx, seconds: int):
        """Modifier le temps entre chaque payday"""
        server = ctx.message.server
        self.settings[server.id]["PAYDAY_TIME"] = seconds
        await self.bot.say("{} secondes entre chaque payday "
                           "et oui !.".format(seconds))
        dataIO.save_json(self.file_path, self.settings)

    @economyset.command(pass_context=True)
    async def paydaycredits(self, ctx, credits: int):
        """Modifier la valeur de chaque payday"""
        server = ctx.message.server
        self.settings[server.id]["PAYDAY_CREDITS"] = credits
        await self.bot.say("Chaque payday donnera maintenant {}$."
                           "".format(credits))
        dataIO.save_json(self.file_path, self.settings)

    @economyset.command(pass_context=True)
    async def registercredits(self, ctx, credits: int):
        """Argent donné à la création d'un compte"""
        server = ctx.message.server
        if credits < 0:
            credits = 0
        self.settings[server.id]["REGISTER_CREDITS"] = credits
        await self.bot.say("Créer un compte donnera désormais {}$."
                           "".format(credits))
        dataIO.save_json(self.file_path, self.settings)

    # What would I ever do without stackoverflow?
    def display_time(self, seconds, granularity=2):
        intervals = (  # Source: http://stackoverflow.com/a/24542445
            ('semaines', 604800),  # 60 * 60 * 24 * 7
            ('jours', 86400),    # 60 * 60 * 24
            ('heures', 3600),    # 60 * 60
            ('minutes', 60),
            ('secondes', 1),
        )

        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                result.append("{} {}".format(value, name))
        return ', '.join(result[:granularity])


def check_folders():
    if not os.path.exists("data/economy"):
        print("Creating data/economy folder...")
        os.makedirs("data/economy")


def check_files():

    f = "data/economy/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default economy's settings.json...")
        dataIO.save_json(f, {})

    f = "data/economy/bank.json"
    if not dataIO.is_valid_json(f):
        print("Creating empty bank.json...")
        dataIO.save_json(f, {})


def setup(bot):
    global logger
    check_folders()
    check_files()
    logger = logging.getLogger("red.economy")
    if logger.level == 0:
        # Prevents the logger from being loaded again in case of module reload
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(
            filename='data/economy/economy.log', encoding='utf-8', mode='a')
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(message)s', datefmt="[%d/%m/%Y %H:%M]"))
        logger.addHandler(handler)
    bot.add_cog(Economy(bot))

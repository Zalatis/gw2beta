import discord
from discord.ext import commands
from discord.utils import find
from __main__ import send_cmd_help
import platform, asyncio, string, operator, random, textwrap
import os, re, aiohttp
from .utils.dataIO import fileIO
from cogs.utils.dataIO import dataIO
from cogs.utils import checks
import time
import json
import random
import re
try:
    import scipy
    import scipy.misc
    import scipy.cluster
except:
    pass

prefix = fileIO("data/red/settings.json", "load")['PREFIXES']

dev = ["167252036444880896"]

class AlcherRPG:
    """Jeu RPG"""
    def __init__(self, bot):
        self.bot = bot

    def _is_mention(self,user):
        if "mention" not in self.settings.keys() or self.settings["mention"]:
            return user.mention
        else:
            return user.name

    async def check_answer(self, ctx, valid_options):

        answer = await self.bot.wait_for_message(author=ctx.message.author, channel=ctx.message.channel)

        if answer.content.lower() in valid_options:
            return answer.content

        elif answer.content in valid_options:
            return answer.content

        elif answer.content.upper() in valid_options:
            return answer.content

        else:
            return await self.check_answer(ctx, valid_options)

    @commands.command (pass_context = True)
    async def jouer(self, ctx):
        """Création du personnage"""
        channel = ctx.message.channel
        server = channel.server
        user = ctx.message.author
        await self._create_user(user, server)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")

        if not userinfo["class"] == "None" and not userinfo["race"] == "None":
            await self.bot.reply("Voulez-vous redémarrer ?")
            answer1 = await self.check_answer(ctx, ["oui", "non", "n", "o", "!jouer"])

            if answer1 == "!jouer":
                pass
            elif answer1 == "o" or answer1 == "O" or answer1 == "oui" or answer1 == "Oui":
                userinfo["gold"] = 0
                userinfo["race"] = "None"
                userinfo["class"] = "None"
                userinfo["enemieskilled"] = 0
                userinfo["equip"] = "None"
                userinfo["inventory"] = []
                userinfo["health"] = 100
                userinfo["deaths"] = 0
                userinfo["hp_potions"] = 0
                userinfo["inguild"] = "None"
                userinfo["guildhash"] = 0
                userinfo["lootbag"] = 0
                userinfo["name"] = user.name
                userinfo["location"] = "Golden Temple"
                userinfo["selected_enemy"] = "None"
                userinfo["quoti_block"] = 0
                userinfo["rest_block"] = 0
                userinfo["in_dungeon"] = "False"
                userinfo["duneon_enemy_hp"] = 0
                userinfo["dungeon_enemy"] = "None"
                userinfo["wearing"] = "None"
                userinfo["keys"] = 0
                userinfo["roaming"] = "False"
                userinfo["lvl"] = 0
                userinfo["chop_block"] = 0
                userinfo["mine_block"] = 0
                userinfo["in_party"] = []
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                await self.bot.say("Vous avez été réinitialisé! Veuillez utiliser `!jouer` à nouveau.")
                return
            elif answer1 == "n" or answer1 == "N" or answer1 == "non" or answer1 == "Non":
                await self.bot.say("Ok then")
                return

        await self.bot.say("Bonjour {}".format(user.name))
        await asyncio.sleep(2)
        await self.bot.say("Bienvenue sur Discord Dungeon\n\nPuis-je vous demander de quelle race vous êtes?\n`Choisissez-en une`\nOrc\nHumain\nSylvari")

        answer1 = await self.check_answer(ctx, ["orc", "humain", "sylvari", "!jouer"])

        if answer1 == "!jouer":
            pass
        elif answer1 == "orc" or answer1 == "Orc":
            userinfo["race"] = "Orc"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
        elif answer1 == "humain" or answer1 == "Humain":
            userinfo["race"] = "Humain"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
        elif answer1 == "sylvari" or answer1 == "Sylvari":
            userinfo["race"] = "Sylvari"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

        await self.bot.reply("Bien!\nDe quelle classe es-tu?\n`Choisissez-en une`\nArcher\nPaladin\nMage\nVoleur")

        answer2 = await self.check_answer(ctx, ["archer", "paladin", "mage", "voleur", "!jouer"])

        if answer2 == "!jouer":
            return

        elif answer2 == "archer" or answer2 == "Archer":
            userinfo["class"] = "Archer"
            userinfo["skills_learned"].append("Shoot")
            userinfo["equip"] = "Simple Bow"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            await self.bot.say("Bien, profitez de votre séjour!")
            return
        elif answer2 == "paladin" or answer2 == "Paladin":
            userinfo["class"] = "Paladin"
            userinfo["skills_learned"].append("Swing")
            userinfo["equip"] = "Simple Sword"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            await self.bot.say("Bien, profitez de votre séjour!")
            return
        elif answer2 == "mage" or answer2 == "Mage":
            userinfo["class"] = "Mage"
            userinfo["skills_learned"].append("Cast")
            userinfo["equip"] = "Simple Staff"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            await self.bot.say("Bien, profitez de votre séjour!")
            return
        elif answer2 == "voleur" or answer2 == "Voleur":
            userinfo["class"] = "Voleur"
            userinfo["skills_learned"].append("Stab")
            userinfo["equip"] = "Simple Dagger"
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            await self.bot.say("Bien, profitez de votre séjour!")
            return

    @commands.command(pass_context = True)
    async def combattre(self, ctx):
        """Combattre un ennemi"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return

        if userinfo["health"] <= 0:
            await self.bot.reply("Vous ne pouvez pas vous battre avec 0 HP")
            return

        if userinfo["location"] == "Golden Temple":
            monsterlist = ["Rachi", "Debin", "Oofer"]
        elif userinfo["location"] == "The Forest":
            monsterlist = ["Wolf", "Goblin", "Zombie"]
        elif userinfo["location"] == "Saker Keep":
            monsterlist = ["Draugr", "Stalker", "Souleater"]

        #IF PLAYER ISNT FIGHTING AN ENEMY, Choisissez-en une BASED ON LOCATION
        if userinfo["selected_enemy"] == "None":
            debi = random.choice((monsterlist))
            await self.bot.say("Vous vous baladez dans {} et tombez sur {}.\nVoulez-vous le combattre? **O** ou **N**".format(userinfo["location"], debi))
            options = ["o", "O", "oui", "Oui", "n", "N", "Non", "non", "!combattre"]
            answer1 = await self.check_answer(ctx, options)

            if answer1 == "!combattre":
                pass

            if answer1 == "o" or answer1 == "O" or answer1 == "Oui" or answer1 == "oui":
                userinfo["selected_enemy"] = debi
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

                if userinfo["selected_enemy"] == "Rachi" or userinfo["selected_enemy"] == "Draugr":
                    userinfo["enemyhp"] = random.randint(50, 75)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                elif userinfo["selected_enemy"] == "Debin" or userinfo["selected_enemy"] == "Stalker":
                    userinfo["enemyhp"] = random.randint(50, 100)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                elif userinfo["selected_enemy"] == "Oofer" or userinfo["selected_enemy"] == "Souleater":
                    userinfo["enemyhp"] = random.randint(75, 125)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)    
                elif userinfo["selected_enemy"] == "Wolf":
                    userinfo["enemyhp"] = random.randint(150, 200)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo) 
                elif userinfo["selected_enemy"] == "Goblin":
                    userinfo["enemyhp"] = random.randint(125, 150)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)  
                elif userinfo["selected_enemy"] == "Zombie":
                    userinfo["enemyhp"] = random.randint(175, 225)
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo) 
            elif answer1 == "n" or answer1 == "N" or answer1 == "non" or answer1 == "Non":
                await self.bot.say("Ok then.")
                return
        #YOUR DAMAGE BASED ON THE WEAPON YOUR HOLDING
        youdmg = 0
        if userinfo["equip"] == "Simple Dagger":
            youdmg += random.randint(5, 25)
        elif userinfo["equip"] == "Simple Staff":
            youdmg += random.randint(5, 25)
        elif userinfo["equip"] == "Simple Bow":
            youdmg += random.randint(5, 25)
        elif userinfo["equip"] == "Simple Sword":
            youdmg += random.randint(5, 25)
        elif userinfo["equip"] == "Sprine Dagger":
            youdmg += random.randint(10, 60)
        elif userinfo["equip"] == "Sprine Staff":
            youdmg += random.randint(10, 60)
        elif userinfo["equip"] == "Sprine Bow":
            youdmg += random.randint(10, 60)
        elif userinfo["equip"] == "Sprine Sword":
            youdmg += random.randint(10, 60)

        #ENEMY DAMAGE BASED ON ENEMY GROUPS
        enemydmg = 0

        if userinfo["selected_enemy"] == "Rachi" or userinfo["selected_enemy"] == "Draugr":
            enemydmg += random.randint(0, 10)
            enemygold = random.randint(25, 40)
            goldlost = random.randint(0, 60)
            xpgain = random.randint(5, 10)
        elif userinfo["selected_enemy"] == "Debin" or userinfo["selected_enemy"] == "Stalker":
            enemydmg += random.randint(0, 20)
            enemygold = random.randint(25, 50)
            goldlost = random.randint(0, 70)
            xpgain = random.randint(5, 20)
        elif userinfo["selected_enemy"] == "Oofer" or userinfo["selected_enemy"] == "Souleater":
            enemydmg += random.randint(0, 30)
            enemygold = random.randint(35, 70)
            goldlost = random.randint(0, 80)
            xpgain = random.randint(10, 25)
        elif userinfo["selected_enemy"] == "Wolf":
            enemydmg += random.randint(10, 40)
            enemygold = random.randint(40, 90)
            goldlost = random.randint(0, 160)
            xpgain = random.randint(10, 30)
        elif userinfo["selected_enemy"] == "Goblin":
            enemydmg += random.randint(10, 60)
            enemygold = random.randint(40, 140)
            goldlost = random.randint(0, 160)
            xpgain = random.randint(10, 30)
        elif userinfo["selected_enemy"] == "Zombie":
            enemydmg += random.randint(10, 40)
            enemygold = random.randint(40, 90)
            goldlost = random.randint(0, 160)
            xpgain = random.randint(10, 30)

        #YOUR SKILL OPTIONS LIST
        show_list = []
        options = ["!combattre"]
        if "Swing" in userinfo["skills_learned"]:
            options.append("swing")
            options.append("Swing")
            show_list.append("Swing")
        elif "Stab" in userinfo["skills_learned"]:
            options.append("stab")
            options.append("Stab")
            show_list.append("Stab")
        elif "Shoot" in userinfo["skills_learned"]:
            options.append("shoot")
            options.append("Shoot")
            show_list.append("Shoot")
        elif "Cast" in userinfo["skills_learned"]:
            options.append("cast")
            options.append("Cast")
            show_list.append("Cast")
        #IF FOR WHATEVER REASON THE USER DOES !combattre AGAIN, RETURN
        em = discord.Embed(description="<@{}> ```diff\n+ Quelle compétence voudriez-vous utiliser?\n\n- Choisissez-en une\n+ {}```".format(user.id, "\n+".join(show_list)), color=discord.Color.blue())
        await self.bot.say(embed=em)
        answer2 = await self.check_answer(ctx, options)

        if answer2 == "!combattre":
            return

        #DEFINE WHAT SKILL WE SELECTED
        if answer2 == "cast" or answer2 == "Cast":
            move = "Cast"
        elif answer2 == "shoot" or answer2 == "Shoot":
            move = "Shoot"
        elif answer2 == "swing" or answer2 == "Swing":
            move = "Swing"
        elif answer2 == "stab" or answer2 == "Stab":
            move = "Stab"

        #LETS DEFINE OUR VAR'S
        userhealth = userinfo["health"]
        userhealth1 = userhealth
        userhealth = userhealth - enemydmg
        userlvl = userinfo["lvl"]
        lvlexp = 100 * userlvl

        #LETS DEFINE THE ENEMY'S VAR'S
        enemyhp = userinfo["enemyhp"]
        enemyhp1 = enemyhp
        enemyhp = enemyhp - youdmg
        lootbag = random.randint(1, 10)

        #IF SELECTED A SKILL, FIGHT
        if answer2 in options:
            if enemydmg < 0:
                enemydmg = 0
            if userhealth < 0:
                userhealth = 0
            if enemyhp < 0:
                enemyhp = 0
            em = discord.Embed(description="```diff\n- {} a {} HP\n+ {} a {} HP\n\n- {} a frappé {} et lui inflige {} points de dégâts\n+ {} utilise {} et inflige {} points de dégâts\n\n- {} a {} HP restants\n+ {} a {} HP restants```".format(userinfo["selected_enemy"], userinfo["enemyhp"], userinfo["name"], userinfo["health"], userinfo["selected_enemy"], userinfo["name"], enemydmg, userinfo["name"], move, youdmg, userinfo["selected_enemy"], enemyhp, userinfo["name"], userhealth), color=discord.Color.red())
            await self.bot.say(embed=em)
            userinfo["health"] = userhealth
            userinfo["enemyhp"] = enemyhp

            if enemyhp <= 0 and userhealth <= 0:
                em = discord.Embed(description="```diff\n- {} vous a tué\n- {} a perdu {} Or.```".format(userinfo["selected_enemy"], userinfo["name"], goldlost), color=discord.Color.red())
                await self.bot.say(embed=em)
                userinfo["gold"] = userinfo["gold"] - goldlost
                if userinfo["gold"] < 0:
                    userinfo["gold"] = 0
                if userinfo["health"] < 0:
                    userinfo["health"] = 0
                userinfo["health"] = 0
                userinfo["selected_enemy"] = "None"
                userinfo["enemieskilled"] = userinfo["enemieskilled"] + 1
                userinfo["deaths"] = userinfo["deaths"] + 1
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

            elif userhealth <= 0:
                em = discord.Embed(description="```diff\n- {} a tué {}\n- {} a perdu {} Or```".format(userinfo["selected_enemy"], userinfo["name"], userinfo["name"], goldlost), color=discord.Color.red())
                await self.bot.say(embed=em)
                userinfo["gold"] = userinfo["gold"] - goldlost
                if userinfo["gold"] < 0:
                    userinfo["gold"] = 0
                if userinfo["health"] < 0:
                    userinfo["health"] = 0
                userinfo["selected_enemy"] = "None"
                userinfo["deaths"] = userinfo["deaths"] + 1
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

            elif enemyhp <= 0:
                em = discord.Embed(description="```diff\n+ {} a tué le {}\n+ {} a gagné {} Or\n+ {} a gagné {} Exp```".format(userinfo["name"], userinfo["selected_enemy"], userinfo["name"], enemygold, userinfo["name"], xpgain), color=discord.Color.blue())
                await self.bot.say(embed=em)
                userinfo["selected_enemy"] = "None"
                userinfo["gold"] = userinfo["gold"] + enemygold
                userinfo["exp"] = userinfo["exp"] + xpgain
                print(lootbag)
                if lootbag == 6:
                    em = discord.Embed(description="```diff\n+ {} Obtient un sac à butin!```".format(userinfo["name"]), color=discord.Color.blue())
                    await self.bot.say(embed=em)
                    userinfo["lootbag"] = userinfo["lootbag"] + 1
                    fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                userinfo["enemieskilled"] = userinfo["enemieskilled"] + 1
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

            if userinfo["exp"] >= lvlexp:
                em = discord.Embed(description="```diff\n+ {} gagne un niveau!```".format(userinfo["name"]), color=discord.Color.blue())
                await self.bot.say(embed=em)
                userinfo["lvl"] = userinfo["lvl"] + 1
                userinfo["health"] = 100
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

    @commands.command(pass_context=True)
    async def sac(self, ctx):
        """Ouvre un sac à butin"""
        channel = ctx.message.channel
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        if userinfo["lootbag"] == 0:
            em = discord.Embed(description="```diff\n- Vous n'avez pas de sac à butin!```", color=discord.Color.blue())
            await self.bot.say(embed=em)
            return
        else:
            em = discord.Embed(description="```diff\n+ {} Ouverture du sac à butin. . .```".format(userinfo["name"]), color=discord.Color.blue())
            await self.bot.say(embed=em)
            await asyncio.sleep(5)
            chance = random.randint(1, 3)
            goldmul = random.randint(10, 30)
            goldgain = goldmul * userinfo["lvl"]
            if chance == 3:
                em = discord.Embed(description="```diff\n+ Vous trouvez {} Or dans le sac!```".format(goldgain), color=discord.Color.blue())
                await self.bot.say(embed=em)
                userinfo["gold"] = userinfo["gold"] + goldgain
                userinfo["lootbag"] = userinfo["lootbag"] - 1
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            else:
                em = discord.Embed(description="```diff\n- Le sac ne contenait rien!```", color=discord.Color.blue())
                await self.bot.say(embed=em)
                userinfo["lootbag"] = userinfo["lootbag"] - 1
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

    @commands.command (pass_context = True)
    async def voyage(self, ctx):
        """Vous permet de changer d'emplacement"""
        channel = ctx.message.channel
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        options = []
        options2 = []
        travel_location = []

        if userinfo["lvl"] > 0:
            options.append("(0) Golden Temple")
            options2.append("0")

            options.append("(1) Saker Keep")
            options2.append("1")

        if userinfo["lvl"] >= 10:
            options.append("(2) The Forest")
            options2.append("2")

        em = discord.Embed(description="<@{}>\n```diff\n+ Où veux-tu partir en voyage?\n- Tape le numéro de l'emplacement.\n+ {}```".format(user.id, "\n+ ".join(options)), color=discord.Color.blue())
        await self.bot.say(embed=em)

        answer1 = await self.check_answer(ctx, options2)

        if answer1 == "0":
            if userinfo["location"] == "Golden Temple":
                em = discord.Embed(description="<@{}>\n```diff\n- Vous êtes déjà à {}!```".format(user.id, userinfo["location"]), color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            else:
                location_name = "Golden Temple"
                userinfo["location"] = "Golden Temple"

        elif answer1 == "1":
            if userinfo["location"] == "Saker Keep":
                em = discord.Embed(description="<@{}>\n```diff\n- Vous êtes déjà à {}!```".format(user.id, userinfo["location"]), color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            else:
                location_name = "Saker Keep"
                userinfo["location"] = "Saker Keep"

        elif answer1 == "2":
            if userinfo["location"] == "The Forest":
                em = discord.Embed(description="<@{}>\n```diff\n- Vous êtes déjà à {}!```".format(user.id, userinfo["location"]), color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            else:
                location_name = "The Forest"
                userinfo["location"] = "The Forest"

        em = discord.Embed(description="<@{}>\n```diff\n+ Voyage en cours vers {}...```".format(user.id, location_name), color=discord.Color.red())
        await self.bot.say(embed=em)
        await asyncio.sleep(3)
        userinfo["location"] = location_name
        fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
        await self.bot.say("Vous êtes arrivé à {}".format(location_name))
        em = discord.Embed(description="<@{}>\n```diff\n+ Vous êtes arrivé à {}```".format(user.id, location_name), color=discord.Color.red())
        await self.bot.say(embed=em)

    @commands.command(pass_context = True)
    async def inventaire(self, ctx):
        """Montre votre inventaire"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        em = discord.Embed(description="```diff\n!== [Inventaire de {}] ==!\n\n!==== [Équipement] ====!\n+ Or : {}\n+ Bois : {}\n+ Pierre : {}\n+ Métal : {}\n\n!===== [Objets] =====!\n+ Clés : {}\n+ Sac à butin : {}\n+ Potions de soin mineur : {}\n+ {}```".format(userinfo["name"], userinfo["gold"], userinfo["wood"], userinfo["stone"], userinfo["metal"], userinfo["keys"], userinfo["lootbag"], userinfo["hp_potions"], "\n+ ".join(userinfo["inventory"])), color=discord.Color.blue())
        await self.bot.say(embed=em)

    @commands.command(pass_context = True)
    async def stats(self, ctx):
        """Montre vos stats"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        maxexp = 100 * userinfo["lvl"]
        em = discord.Embed(description="```diff\n!== [Stats de {}] ==!\n+ Nom : {}\n+ Titre : {}\n+ Race : {}\n+ Classe : {}\n\n+ Niveau : {} | Exp : ({}/{})\n+ Vie : ({}/100)\n+ Stamina : {}\n+ Mana : {}\n\n!===== [Equipment] =====!\n+ Arme : {}\n+ Équipé : {}\n\n+ Tué : {} Ennemis\n+ Mort : {} Fois```".format(userinfo["name"], userinfo["name"], userinfo["title"], userinfo["race"], userinfo["class"], userinfo["lvl"], userinfo["exp"], maxexp, userinfo["health"], userinfo["stamina"], userinfo["mana"], userinfo["equip"], userinfo["wearing"], userinfo["enemieskilled"], userinfo["deaths"]), color=discord.Color.blue())
        await self.bot.say(embed=em)

    @commands.command(pass_context = True)
    async def equiper(self, ctx):
        """Equiper un objet que vous avez dans votre inventaire"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        choices = []
        inv_list = [i for i in userinfo["inventory"]]
        if len(inv_list) == 0:
            em = discord.Embed(description="```diff\n- Vous n'avez rien d'autre à équiper!```", color=discord.Color.red())
            await self.bot.say(embed=em)
        else:
            choices.append(inv_list)
            em = discord.Embed(description="```diff\n+ Que voudriez-vous équiper??\n- Notez que ceci est sensible aux majuscules et minuscules.\n{}```".format("\n".join(inv_list)), color=discord.Color.blue())
            await self.bot.say(embed=em)
            answer1 = await self.check_answer(ctx, inv_list)
            await self.bot.say("Vous avez équipé: {}!".format(answer1))
            em = discord.Embed(description="```diff\n+ Vous avez équipé: {}!```".format(answer1), color=discord.Color.blue())
            await self.bot.say(embed=em)
            userinfo["inventory"].append(userinfo["equip"])
            userinfo["equip"] = "None"
            userinfo["equip"] = answer1
            userinfo["inventory"].remove(answer1)
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)

    @commands.group(pass_context = True)
    async def acheter(self, ctx):
        """Acheter de l'équipement"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        weapons_list = ["hp","Hp", "Sprine sword", "sprine sword", "Sprine bow", "sprine bow", "Sprine dagger", "sprine dagger", "Sprine staff", "sprine staff"]
        if ctx.invoked_subcommand is None:
            em = discord.Embed(description="```!acheter item_name\n\nNote: Tout doit être en minuscule.```", color=discord.Color.blue())
            await self.bot.say(embed=em)

    @acheter.command(pass_context=True)
    async def hp(self, ctx, *, ammount : int):
        """Acheter une potion de soin"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        Sum = ammount * 30

        if ammount == None:
            ammount = 1

        if userinfo["gold"] < Sum:
            needed = Sum - userinfo["gold"]
            em = discord.Embed(description="```diff\n- Vous avez besion de {} Or supplémentaire pour pouvoir acheter {} potion(s)```".format(needed, ammount), color=discord.Color.red())
            await self.bot.say(embed=em)
        else:   
            userinfo["gold"] = userinfo["gold"] - Sum
            userinfo["hp_potions"] = userinfo["hp_potions"] + int(ammount)
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n+ Vous avez acheté {} potion(s) pour {} Or```".format(ammount, Sum), color=discord.Color.blue())
            await self.bot.say(embed=em)

    @acheter.command(pass_context=True)
    async def item(self, ctx, *, item):
        """Acheter de l'équipement"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if item == "sprine sword":
            if not userinfo["class"] == "Paladin":
                em = discord.Embed(description="```diff\n- Vous devez être un Paladin pour acheter cet objet.```", color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            cost = 1000
            value = cost - userinfo["gold"]
            if userinfo["gold"] < cost:
                em = discord.Embed(description="```diff\n- Vous avez besoin de {} Or supplémentaire pour pouvoir acheter cet objet.```".format(value), color=discord.Color.red())
                await self.bot.say(embed=em)
            else:
                cost = 1000
                userinfo["gold"] = userinfo["gold"] - cost
                userinfo["inventory"].append("Sprine Sword")
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                em = discord.Embed(description="```diff\n+ Vous avez acheté l'objet pour {} Or.```".format(cost), color=discord.Color.blue())
                await self.bot.say(embed=em)

        elif item == "sprine dagger":
            if not userinfo["class"] == "Voleur":
                em = discord.Embed(description="```diff\n- Vous devez être un Voleur pour acheter cet objet.```", color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            cost = 1000
            value = cost - userinfo["gold"]
            if userinfo["gold"] < cost:
                em = discord.Embed(description="```diff\n- Vous avez besoin de {} Or supplémentaire pour pouvoir acheter cet objet.```".format(value), color=discord.Color.red())
                await self.bot.say(embed=em)
            else:
                cost = 1000
                userinfo["gold"] = userinfo["gold"] - cost
                userinfo["inventory"].append("Sprine Dagger")
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                em = discord.Embed(description="```diff\n+ Vous avez acheté l'objet pour {} Or.```".format(cost), color=discord.Color.blue())
                await self.bot.say(embed=em)

        elif item == "sprine bow":
            if not userinfo["class"] == "Archer":
                em = discord.Embed(description="```diff\n- Vous devez être un archer pour acheter cet objet.```", color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            cost = 1000
            value = cost - userinfo["gold"]
            if userinfo["gold"] < cost:
                em = discord.Embed(description="```diff\n- Vous avez besoin de {} Or supplémentaire pour pouvoir acheter cet objet.```".format(value), color=discord.Color.red())
                await self.bot.say(embed=em)
            else:
                cost = 1000
                userinfo["gold"] = userinfo["gold"] - cost
                userinfo["inventory"].append("Sprine Bow")
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                em = discord.Embed(description="```diff\n+ Vous avez acheté l'objet pour {} Or.```".format(cost), color=discord.Color.blue())
                await self.bot.say(embed=em)

        elif item == "sprine staff":
            if not userinfo["class"] == "Mage":
                em = discord.Embed(description="```diff\n- Vous devez être un Mage pour acheter cet objet.```", color=discord.Color.red())
                await self.bot.say(embed=em)
                return
            cost = 1000
            value = cost - userinfo["gold"]
            if userinfo["gold"] < cost:
                em = discord.Embed(description="```diff\n- Vous avez besoin de {} Or supplémentaire pour pouvoir acheter cet objet.```".format(value), color=discord.Color.red())
                await self.bot.say(embed=em)
            else:
                cost = 1000
                userinfo["gold"] = userinfo["gold"] - cost
                userinfo["inventory"].append("Sprine Staff")
                fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
                em = discord.Embed(description="```diff\n+ Vous avez acheté l'objet pour {} Or.```".format(cost), color=discord.Color.blue())
                await self.bot.say(embed=em)
        else:
            em = discord.Embed(description="```diff\n- Vous voulez acheter un objet invalide.\n\n+ Pour voir la liste des objets disponibles, tapez !items```", color=discord.Color.red())
            await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def items(self, ctx, *, Class):
        """Liste les objets pour les différentes classes"""
        user = ctx.message.author
        if Class == "Mage" or Class == "mage":
            em = discord.Embed(description="```diff\n+ Liste d'objets pour la classe Mage.```\n\n1) Sprine Staff - [1,000 Gold]", color=discord.Color.blue())
            await self.bot.say(embed=em)
        elif Class == "Paladin" or Class == "paladin":
            em = discord.Embed(description="```diff\n+ Liste d'objets pour la classe Paladin.```\n\n1) Sprine Sword - [1,000 Gold]", color=discord.Color.blue())
            await self.bot.say(embed=em)
        elif Class == "Voleur" or Class == "voleur":
            em = discord.Embed(description="```diff\n+ Liste d'objets pour la classe Voleur.```\n\n1) Sprine Dagger - [1,000 Gold]", color=discord.Color.blue())
            await self.bot.say(embed=em)
        elif Class == "Archer" or Class == "archer":
            em = discord.Embed(description="```diff\n+ Liste d'objets pour la classe Archer.```\n\n1) Sprine Bow - [1,000 Gold]", color=discord.Color.blue())
            await self.bot.say(embed=em)
        else:
            em = discord.Embed(description="```diff\n- Ce n'est pas une classe valide.```", color=discord.Color.red())
            await self.bot.say(embed=em)

    @commands.command(pass_context = True)
    async def heal(self, ctx):
        """Utilise votre potion de soin mineure"""
        user = ctx.message.author
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        if userinfo["hp_potions"] > 0:
            gain = random.randint(90, 100)
            userinfo["health"] = userinfo["health"] + gain
            if userinfo["health"] > 100:
                userinfo["health"] = 100
            userinfo["hp_potions"] = userinfo["hp_potions"] - 1
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n- Vous utilisez une Potion de soin mineure\n+ {} HP```".format(gain), color=discord.Color.red())
            await self.bot.say(embed=em)
        else:
            em = discord.Embed(description="```diff\n- Vous n'avez aucune potion de soin!```", color=discord.Color.red())
            await self.bot.say(embed=em)


    @commands.command(pass_context=True)
    async def quoti(self, ctx):
        """Vous donne chaque jour de l'Or"""
        channel = ctx.message.channel
        user = ctx.message.author
        goldget = random.randint(500, 1000)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        curr_time = time.time()
        delta = float(curr_time) - float(userinfo["quoti_block"])

        if delta >= 86400.0 and delta>0:
            if userinfo["class"] == "None" and userinfo["race"] == "None":
                await self.bot.reply("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
                return
            userinfo["gold"] += goldget
            userinfo["quoti_block"] = curr_time
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n+ Voici votre bourse d'Or quotidienne!\n+ Vous récupérez {} Or```".format(goldget), color=discord.Color.blue())
            await self.bot.say(embed=em)
        else:
            # calulate time left
            seconds = 86400 - delta
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            em = discord.Embed(description="```diff\n- Vous ne pouvez pas encore réclamer votre récompense quotidienne!\n\n- Temps restant:\n- {} Heures, {} Minutes, et {} Secondes```".format(int(h), int(m), int(s)), color=discord.Color.red())
            await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def repos(self, ctx):
        """Vous permet de vous reposer pour récupérer des HP"""
        channel = ctx.message.channel
        user = ctx.message.author
        HPget = random.randint(10, 40)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        curr_time = time.time()
        delta = float(curr_time) - float(userinfo["rest_block"])

        if delta >= 120.0 and delta>0:
            if userinfo["class"] == "None" and userinfo["race"] == "None":
                await self.bot.reply("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
                return
            userinfo["health"] = userinfo["health"] + HPget
            if userinfo["health"] > 100:
                userinfo["health"] = 100
            userinfo["rest_block"] = curr_time
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n+ Vous récupérez {} HP pour vous être reposé!```".format(HPget), color=discord.Color.blue())
            await self.bot.say(embed=em)
        else:
            # calulate time left
            seconds = 120 - delta
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            em = discord.Embed(description="```diff\n- Tu n'es pas fatigué!\n\n- Temps restant:\n- {} Heures, {} Minutes, et {} Secondes```".format(int(h), int(m), int(s)), color=discord.Color.red())
            await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def miner(self, ctx):
        """Miner un rocher"""
        channel = ctx.message.channel
        user = ctx.message.author
        mined_metal = random.randint(1, 10)
        mined_rock = random.randint(1, 10)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        curr_time = time.time()
        delta = float(curr_time) - float(userinfo["mine_block"])

        if delta >= 600.0 and delta>0:
            if userinfo["class"] == "None" and userinfo["race"] == "None":
                await self.bot.reply("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
                return
            userinfo["metal"] = userinfo["metal"] + mined_metal
            userinfo["stone"] = userinfo["stone"] + mined_rock
            userinfo["mine_block"] = curr_time
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n+ Vous avez miné un rocher!\n+ {} Métal\n+ {} Pierre```".format(mined_metal, mined_rock), color=discord.Color.blue())
            await self.bot.say(embed=em)
        else:
            # calulate time left
            seconds = 600 - delta
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            em = discord.Embed(description="```diff\n- Vous ne pouvez pas encore miner!\n\n- Temps restant:\n- {} Heures, {} Minutes, et {} Secondes```".format(int(h), int(m), int(s)), color=discord.Color.red())
            await self.bot.say(embed=em)

    @commands.command(pass_context=True)
    async def couper(self, ctx):
        """Couper un arbre"""
        channel = ctx.message.channel
        user = ctx.message.author
        chopped = random.randint(1, 10)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")
        if userinfo["race"] and userinfo["class"] == "None":
            await self.bot.say("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
            return
        curr_time = time.time()
        delta = float(curr_time) - float(userinfo["chop_block"])

        if delta >= 600.0 and delta>0:
            if userinfo["class"] == "None" and userinfo["race"] == "None":
                await self.bot.reply("S'il vous plaît, créez votre personnage en utilisant `!jouer`")
                return
            userinfo["wood"] = userinfo["wood"] + chopped
            userinfo["chop_block"] = curr_time
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", userinfo)
            em = discord.Embed(description="```diff\n+ Vous avez coupé un arbre!\n+ {} Bois```".format(chopped), color=discord.Color.blue())
            await self.bot.say(embed=em)
        else:
            # calulate time left
            seconds = 600 - delta
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            em = discord.Embed(description="```diff\n- Vous ne pouvez pas couper d'arbre pour le moment!\n\n- Temps restant:\n- {} Heures, {} Minutes, et {} Secondes```".format(int(h), int(m), int(s)), color=discord.Color.red())
            await self.bot.say(embed=em)


    def _name(self, user, max_length):
        if user.name == user.display_name:
            return user.name
        else:
            return "{} ({})".format(user.name, self._truncate_text(user.display_name, max_length - len(user.name) - 3), max_length)

    async def on_message(self, message):
        await self._handle_on_message(message)

    async def _handle_on_message(self, message):
        text = message.content
        channel = message.channel
        server = message.server
        user = message.author
        # creates user if doesn't exist, bots are not logged.
        await self._create_user(user, server)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")

    # handles user creation.
    async def _create_user(self, user, server):
        if not os.path.exists("data/alcher/players/{}".format(user.id)):
            os.makedirs("data/alcher/players/{}".format(user.id))
            new_account = {
                "name": user.name,
                "race": "None",
                "class": "None",
                "health": 100,
                "enemyhp": 50,
                "enemylvl": 0,
                "lvl": 0,
                "gold": 0,
                "wood": 0,
                "metal": 0,
                "stone": 0,
                "enemieskilled": 0,
                "selected_enemy": "None",
                "deaths": 0,
                "exp": 0,
                "lootbag": 0,
                "wearing": "None",
                "defence": 0,
                "guild": "None",
                "inguild": "None",
                "skills_learned": [],
                "inventory" : [],
                "equip": "None",
                "title": "None",
                "wincry": "None",
                "losecry": "None",
                "location": "Golden Temple",
                "roaming": "False",
                "pet": "None",
                "mana": 100,
                "stamina": 100,
                "craftable": [],
                "quoti_block": 0,
                "rest_block": 0,
                "fight_block": 0,
                "traveling_block": 0,
                "hp_potions": 0,
                "keys": 0,
                "mine_block": 0,
                "chop_block": 0,
                "in_dungeon": "False",
                "dungeon_enemy": "None",
                "duneon_enemy_hp": 0,
                "in_party": []
            }
            fileIO("data/alcher/players/{}/info.json".format(user.id), "save", new_account)
        userinfo = fileIO("data/alcher/players/{}/info.json".format(user.id), "load")

def check_folders():
    if not os.path.exists("data/alcher"):
        print("Creating data/alcher folder...")
        os.makedirs("data/alcher")

    if not os.path.exists("data/alcher/players"):
        print("Creating data/alcher/players folder...")
        os.makedirs("data/alcher/players")
        transfer_info()

def transfer_info():
    players = fileIO("data/alcher/players.json", "load")
    for user_id in players:
        os.makedirs("data/alcher/players/{}".format(user_id))
        # create info.json
        f = "data/alcher/players/{}/info.json".format(user_id)
        if not fileIO(f, "check"):
            fileIO(f, "save", players[user_id])

def setup(bot):
    check_folders()

    n = AlcherRPG(bot)
    bot.add_listener(n.on_message,"on_message")
    bot.add_cog(n)

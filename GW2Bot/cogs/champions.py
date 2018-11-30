import discord
import asyncio
from .utils.dataIO import dataIO
from string import ascii_letters
from .utils import checks
import os
import glob
import re
import aiohttp
import json
import math
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import urllib.request
import py_gg

class Champions:
    """Commandes en rapport avec les champions dans LoL"""

    def __init__(self,bot):
        self.bot = bot
        self.header = {"User-Agent": "User_Agent"}
        self.settings = dataIO.load_json("data/league/settings.json")
        self.summoners = dataIO.load_json("data/league/summoners.json")
        self.champions = dataIO.load_json("data/league/champions.json")
        self.runesdata = dataIO.load_json("data/league/runes.json")
        self.template = Image.open("data/league/template.png")
        self.runestemplate = Image.open("data/league/runestemplate.png")
        py_gg.init(self.settings['api_key'])

    @commands.command(pass_context=True)
    @checks.is_owner()
    async def renewdata(self,ctx,patchver):
        """Mettre à jour la version de LoL"""
        self.champions = await use_api(self,ctx,"http://ddragon.leagueoflegends.com/cdn/" + patchver + "/data/fr_FR/champion.json")
        dataIO.save_json("data/league/champions.json",self.champions)
        self.runesdata = await use_api(self,ctx,"http://ddragon.leagueoflegends.com/cdn/" + patchver + "/data/fr_FR/runesReforged.json")
        dataIO.save_json("data/league/runes.json",self.runesdata)
        await self.bot.send_message(ctx.message.channel,"Terminé. :white_check_mark:")

    @commands.command(pass_context=True)
    async def runes(self,ctx,*champion_list):
        """Donne les runes pour le champion choisi"""
        cnl = ctx.message.channel
        championn = " ".join(champion_list)
        championn = " ".join(w.capitalize() for w in championn.split())
        champion = championn.replace(" ","")
        champion = championn.replace("'","")
        if champion == "Wukong":
            champion = "MonkeyKing"
        try:
            champID = self.champions['data'][champion]['key']
        except:
            await self.bot.send_message(cnl,"Champion introuvable! :x:")
            return
        # Reset the template
        loading = await self.bot.send_message(cnl,"**Chargement...** <a:loading:518048830323687425>")
        self.runestemplate = Image.open("data/league/runestemplate.png")
        options = {"champData" : "hashes"}
        res = py_gg.champions.specific(int(champID),options)
        runeslist = res[0]['hashes']['runehash']['highestCount']['hash']
        count = res[0]['hashes']['runehash']['highestCount']['count']
        winrate = res[0]['hashes']['runehash']['highestCount']['winrate']
        runeslist = runeslist.split("-")
        # Identifying each rune
        for i in self.runesdata:
            if i['id'] == int(runeslist[0]):
                rune10 = { "id" : i['id'], "name" : i['name'] }
                urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + i['icon'],"data/league/tempfiles/rune10.png")
                for j in i['slots'][0]['runes']:
                    if j['id'] == int(runeslist[1]):
                        rune11 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune11.png")
                for j in i['slots'][1]['runes']:
                    if j['id'] == int(runeslist[2]):
                        rune12 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune12.png")
                for j in i['slots'][2]['runes']:
                    if j['id'] == int(runeslist[3]):
                        rune13 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune13.png")
                for j in i['slots'][3]['runes']:
                    if j['id'] == int(runeslist[4]):
                        rune14 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune14.png")
            if i['id'] == int(runeslist[5]):
                rune20 = { "id" : i['id'], "name" : i['name'] }
                urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + i['icon'],"data/league/tempfiles/rune20.png")
                for j in i['slots'][1]['runes']:
                    if j['id'] == int(runeslist[6]):
                        rune21 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune21.png")
                    if j['id'] == int(runeslist[7]):
                        rune22 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune22.png")
                for j in i['slots'][2]['runes']:
                    if j['id'] == int(runeslist[6]):
                        rune21 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune21.png")
                    if j['id'] == int(runeslist[7]):
                        rune22 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune22.png")
                for j in i['slots'][3]['runes']:
                    if j['id'] == int(runeslist[6]):
                        rune21 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune21.png")
                    if j['id'] == int(runeslist[7]):
                        rune22 = { "id" : j['id'], "name" : j['name'] }
                        urllib.request.urlretrieve("https://ddragon.leagueoflegends.com/cdn/img/" + j['icon'],"data/league/tempfiles/rune22.png")
        # await self.bot.send_message(cnl,"First branch: " + rune10['name'] + ", " + rune11['name'] + ", " + rune12['name'] + ", "  + rune13['name'] + ", " + rune14['name'])
        # await self.bot.send_message(cnl,"Second branch: " + rune20['name'] + ", " + rune21['name'] + ", " + rune22['name'])
        # Start drawing onto template
        frunefnt = ImageFont.truetype("data/fonts/Exo2-Black.otf",20)
        krunefnt = ImageFont.truetype("data/fonts/Exo2-Bold.otf",18)
        rrunefnt = ImageFont.truetype("data/fonts/Exo2-Light.otf",18)
        draw = ImageDraw.Draw(self.runestemplate)
        urllib.request.urlretrieve("http://ddragon.leagueoflegends.com/cdn/img/champion/splash/" + champion + "_0.jpg", "data/league/tempfiles/splashart.jpg")
        splashart = Image.open("data/league/tempfiles/splashart.jpg")
        width, height = splashart.size
        left = width - 686
        top = 0
        right = width
        bottom = 552
        splashart = splashart.crop((left, top, right, bottom))
        self.runestemplate.paste(splashart,(0,0))
        tnsprntbg = Image.open("data/league/transparentbg.png")
        tnsprntbg = tnsprntbg.resize((686,552),Image.ANTIALIAS)
        self.runestemplate.paste(tnsprntbg,(0,0),tnsprntbg)
        originalimage = Image.open("data/league/runestemplate.png")
        self.runestemplate.paste(originalimage,(0,0),originalimage)
        # Rune 1, 0
        rune10img = Image.open("data/league/tempfiles/rune10.png")
        rune10img.thumbnail((32,32),Image.ANTIALIAS)
        self.runestemplate.paste(rune10img,(45,117),rune10img)
        draw.text((112,117), rune10['name'], font=frunefnt,fill=(255,255,255))
        # Rune 1, 1
        rune11img = Image.open("data/league/tempfiles/rune11.png")
        rune11img.thumbnail((75,75),Image.ANTIALIAS)
        self.runestemplate.paste(rune11img,(25,187),rune11img)
        draw.text((112,207), rune11['name'], font=krunefnt,fill=(255,255,255))
        # Rune 1, 2
        rune12img = Image.open("data/league/tempfiles/rune12.png")
        rune12img.thumbnail((50,50),Image.ANTIALIAS)
        self.runestemplate.paste(rune12img,(37,292),rune12img)
        draw.text((112,304), rune12['name'], font=rrunefnt,fill=(255,255,255))
        # Rune 1, 3
        rune13img = Image.open("data/league/tempfiles/rune13.png")
        rune13img.thumbnail((50,50),Image.ANTIALIAS)
        self.runestemplate.paste(rune13img,(37,381),rune13img)
        draw.text((112,395), rune13['name'], font=rrunefnt,fill=(255,255,255))
        # Rune 1, 4
        rune14img = Image.open("data/league/tempfiles/rune14.png")
        rune14img.thumbnail((50,50),Image.ANTIALIAS)
        self.runestemplate.paste(rune14img,(37,470),rune14img)
        draw.text((112,484), rune14['name'], font=rrunefnt,fill=(255,255,255))
        # Rune 2, 0
        rune20img = Image.open("data/league/tempfiles/rune20.png")
        rune10img.thumbnail((32,32),Image.ANTIALIAS)
        self.runestemplate.paste(rune20img,(427,117),rune20img)
        draw.text((494,117), rune20['name'], font=frunefnt,fill=(255,255,255))
        # Rune 2, 1
        rune21img = Image.open("data/league/tempfiles/rune21.png")
        rune21img.thumbnail((50,50),Image.ANTIALIAS)
        self.runestemplate.paste(rune21img,(418,203),rune21img)
        draw.text((494,217), rune21['name'], font=rrunefnt,fill=(255,255,255))
        # Rune 2, 2
        rune22img = Image.open("data/league/tempfiles/rune22.png")
        rune22img.thumbnail((50,50),Image.ANTIALIAS)
        self.runestemplate.paste(rune22img,(418,424),rune22img)
        draw.text((494,438), rune22['name'], font=rrunefnt,fill=(255,255,255))
        # Adding Corners
        self.runestemplate = add_corners(self.runestemplate,10)
        self.runestemplate.save("data/league/temp_template.png")
        await self.bot.send_message(cnl,"**Page de runes pour " + championn + ":** ")
        await self.bot.delete_message(loading)
        await self.bot.send_file(cnl,"data/league/temp_template.png")
        os.remove("data/league/temp_template.png")
        files = glob.glob("data/league/tempfiles/*")
        for f in files:
            os.remove(f)

def add_corners(im, rad):
    circle = Image.new('L', (rad * 2, rad * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, rad * 2, rad * 2), fill=255)
    alpha = Image.new('L', im.size, 255)
    w, h = im.size
    alpha.paste(circle.crop((0, 0, rad, rad)), (0, 0))
    alpha.paste(circle.crop((0, rad, rad, rad * 2)), (0, h - rad))
    alpha.paste(circle.crop((rad, 0, rad * 2, rad)), (w - rad, 0))
    alpha.paste(circle.crop((rad, rad, rad * 2, rad * 2)), (w - rad, h - rad))
    im.putalpha(alpha)
    return im

async def use_api(self, ctx,url):
    async with aiohttp.ClientSession(headers=self.header) as session:
        try:
            async with session.get(url) as channel:
                res = await channel.json()
                return res
        except Exception as e:
            await self.bot.send_message(ctx.message.channel,"Erreur: " + str(e))
            return

def setup(bot):
    print("setting up...")
    n = Champions(bot)
    bot.add_cog(n)

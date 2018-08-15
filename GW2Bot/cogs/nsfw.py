import discord
from discord.ext import commands
from __main__ import send_cmd_help
from bs4 import BeautifulSoup
import random


class Nsfw:
    """Commandes NSFW."""

    def __init__(self, bot):
        self.bot = bot
        self.session = self.bot.http.session

    @commands.group(pass_context=True)
    async def nsfw(self, ctx):
        """Commandes NSFW"""
        if ctx.invoked_subcommand is None:
            await send_cmd_help(ctx)

    @nsfw.command(no_pm=True, pass_context=True)
    async def yandere(self, ctx):
        """Image aléatoire de yandere"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("https://yande.re/post/random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="highres").get("href")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def konachan(self, ctx):
        """Image aléatoire de Konachan"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("https://konachan.com/post/random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="highres").get("href")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def e621(self, ctx):
        """Image aléatoire de e621"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("https://e621.net/post/random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="highres").get("href")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def rule34(self, ctx):
        """Image aléatoire de  rule34"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://rule34.xxx/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say('http:' + image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def danbooru(self, ctx):
        """Image aléatoire de Danbooru"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://danbooru.donmai.us/posts/random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say('http://danbooru.donmai.us' + image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def gelbooru(self, ctx):
        """Image aléatoire de Gelbooru"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://www.gelbooru.com/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def tbib(self, ctx):
        """Image aléatoire de DrunkenPumken"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://www.tbib.org/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say("http:" + image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def xbooru(self, ctx):
        """Image aléatoire de Xbooru"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://xbooru.com/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def furrybooru(self, ctx):
        """Image aléatoire de Furrybooru"""
        try:
            query = ("http://furry.booru.org/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def drunkenpumken(self, ctx):
        """Image aléatoire de DrunkenPumken"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("http://drunkenpumken.booru.org/index.php?page=post&s=random")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(no_pm=True, pass_context=True)
    async def lolibooru(self, ctx):
        """Image aléatoire de Lolibooru"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        try:
            query = ("https://lolibooru.moe/post/random/")
            page = await self.session.get(query)
            page = await page.text()
            soup = BeautifulSoup(page, 'html.parser')
            image = soup.find(id="image").get("src")
            image = image.replace(' ', '%20')
            await self.bot.say(image)
        except Exception as e:
            await self.bot.say(":x: **Erreur:** `{}`".format(e))

    @nsfw.command(pass_context=True, no_pm=True)
    async def ysearch(self, ctx, *tags: str):
        """Cherche une Yandere avec un tag"""
        channel_nsfw = await self.is_nsfw(ctx.message.channel)
        if not channel_nsfw:
            return
        if tags == ():
            await self.bot.say(":warning: Il manque un tag.")
        else:
            try:
                tags = ("+").join(tags)
                query = ("https://yande.re/post.json?limit=42&tags=" + tags)
                page = await self.session.get(query)
                json = await page.json()
                if json != []:
                    await self.bot.say(random.choice(json)['jpeg_url'])
                else:
                    await self.bot.say(":warning: Yande.re n'a pas d'images correspondant à votre tag.")
            except Exception as e:
                await self.bot.say(":x: `{}`".format(e))

    async def is_nsfw(self, channel: discord.Channel):
        try:
            _gid = channel.server.id
        except AttributeError:
            return False
        data = await self.bot.http.request(
            discord.http.Route(
                'GET', '/guilds/{guild_id}/channels', guild_id=_gid))
        channeldata = [d for d in data if d['id'] == channel.id][0]
        return channeldata['nsfw']


def setup(bot):
    n = Nsfw(bot)
    bot.add_cog(n)

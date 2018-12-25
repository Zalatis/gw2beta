import discord
from discord.ext import commands

try:
    from bs4 import BeautifulSoup

    soupAvailable = True
except:
    soupAvailable = False
import aiohttp


class LoveCalculator:
    """Calcul l'amour entre deux personnes!"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['lovecalc'])
    async def love(self, lover: discord.Member, loved: discord.Member):
        """Calcul le pourcentage d'amour!"""

        x = lover.display_name
        y = loved.display_name

        url = 'https://www.lovecalculator.com/love.php?name1={}&name2={}'.format(x.replace(" ", "+"),
                                                                                 y.replace(" ", "+"))
        async with aiohttp.get(url) as response:
            soupObject = BeautifulSoup(await response.text(), "html.parser")
            try:
                description = soupObject.find('div', attrs={'class': 'result score'}).get_text().strip()
            except:
                description = 'Trop de messages, pour le moment. Veuillez réessayer ultérieurement.'

        try:
            z = description[:2]
            z = int(z)
            if z > 50:
                emoji = '❤'
            else:
                emoji = '💔'
            title = 'Le pourcentage d\'amour entre {} et {} est de:'.format(x, y)
        except:
            emoji = ''
            title = 'Le bot n\'arrive pas à déterminer votre amour'

        description = emoji + ' ' + description + ' ' + emoji
        em = discord.Embed(title=title, description=description, color=discord.Color.red())
        await self.bot.say(embed=em)


def setup(bot):
    if soupAvailable:
        bot.add_cog(LoveCalculator(bot))
    else:
        raise RuntimeError("You need to run `pip3 install beautifulsoup4`")

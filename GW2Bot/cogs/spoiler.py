import os
import random
import textwrap

import discord
from discord.ext import commands

try:
    from PIL import Image, ImageDraw, ImageFont
    pillowAvailable = True
except:
    pillowAvailable = False


class Spoiler:

    """Hide spoilers using animated GIFs"""

    def __init__(self, bot):
        self.bot = bot
        self.temp_filepath = "data/spoiler/"
        self.line_length = 60
        self.margin = (5, 5)
        self.font = "data/spoiler/UbuntuMono-Regular.ttf"
        self.font_size = 14
        self.font_color = 150
        self.bg_color = 20

    @commands.command(pass_context=True, no_pm=True)
    async def spoiler(self, ctx, *, text: str):
        """Use an animated gif to hide spoiler text"""

        message = ctx.message
        author = message.author.display_name
        title = "Passe la souris sur ce message pour le voir"
        if title == ''.join(text):
            await self.bot.say("Bien essayé :|")
            return

        try:
            await self.bot.delete_message(message)
        except discord.errors.Forbidden:
            await self.bot.say("J'ai besoin de la permission "
                               "'Gérer les messages' pour cacher les spoilers !")

        try:
            fnt = ImageFont.truetype(self.font, self.font_size)
        except OSError:
            await self.bot.say("Erreur lors du chargement de la police "
                               "d'écriture, merci de réinstaller le cog.")
            return

        spoil_lines = []
        for line in text.splitlines():
            spoil_lines.extend(textwrap.wrap(line, self.line_length,
                                             replace_whitespace=False))

        width = fnt.getsize(title)[0] + 50
        height = 0

        for line in spoil_lines:
            size = fnt.getsize(line)
            width = max(width, size[0])
            height += size[1] + 2

        width += self.margin[0]*2
        height += self.margin[1]*2

        spoils = '\n'.join(spoil_lines)

        spoil_img = [self.new_image(width, height) for _ in range(2)]
        spoil_text = [title, spoils]

        for img, txt in zip(spoil_img, spoil_text):
            canvas = ImageDraw.Draw(img)
            try:
                canvas.text(self.margin, txt, font=fnt, fill=self.font_color,
                            spacing=4)
            except TypeError:
                canvas.text(self.margin, txt, font=fnt, fill=self.font_color)

        path = self.temp_filepath + ''.join(random.choice(
                   '0123456789ABCDEF') for i in range(12)) + ".gif"

        spoil_img[0].save(path, format="GIF", save_all=True,
                          append_images=[spoil_img[1]],
                          duration=[0, 0xFFFF], loop=0)
        content = "**" + author + "** a publié un spoiler:"
        await self.bot.send_file(ctx.message.channel, path,
                                 content=content)
        os.remove(path)

    def new_image(self, width, height):
        return Image.new("L", (width, height), self.bg_color)


def check_folders():
    folder = "data/spoiler"
    if not os.path.exists(folder):
        print("Creating {} folder...".format(folder))
        os.makedirs(folder)


def setup(bot):
    check_folders()
    if pillowAvailable:
        bot.add_cog(Spoiler(bot))
    else:
        raise RuntimeError("You need to run `pip3 install pillow`")

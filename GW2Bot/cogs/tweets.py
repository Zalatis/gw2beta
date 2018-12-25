from random import choice as randchoice
from datetime import datetime as dt
from discord.ext import commands
import discord
import asyncio
from .utils.dataIO import dataIO
from .utils import checks
from .utils.chat_formatting import pagify
try:
    import tweepy as tw
    twInstalled = True
except:
    twInstalled = False
import os


numbs = {
    "next": "➡",
    "back": "⬅",
    "exit": "❌"
}


class TweetListener(tw.StreamListener):
    
    def __init__(self, api, bot):
        self.bot = bot
        self.api = api

    
    def on_status(self, status):
        # print(status.text)
        self.bot.dispatch("tweet_status", status)
        if self.bot.is_closed:
            return False
        else:
            return True

    def on_error(self, status_code):
        msg = "Une erreur twitter est survenue! " + str(status_code)
        self.bot.dispatch("tweet_error", msg)
        if status_code in [420, 504, 503, 502, 500, 400, 401, 403, 404]:
            return False

    def on_disconnect(self, notice):
        msg = "Twitter: erreur déconnexion"
        self.bot.dispatch("tweet_error", msg)
        return False

    def on_warning(self, notice):
        msg = "Twitter: surcharge"
        self.bot.dispatch("tweet_error", msg)
        return True


class Tweets():
    """Cog pour afficher les informations de l'API de Twitter"""
    def __init__(self, bot):
        self.bot = bot
        self.settings_file = 'data/tweets/settings.json'
        self.settings = dataIO.load_json(self.settings_file)
        if 'consumer_key' in list(self.settings["api"].keys()):
            self.consumer_key = self.settings["api"]['consumer_key']
        if 'consumer_secret' in list(self.settings["api"].keys()):
            self.consumer_secret = self.settings["api"]['consumer_secret']
        if 'access_token' in list(self.settings["api"].keys()):
            self.access_token = self.settings["api"]['access_token']
        if 'access_secret' in list(self.settings["api"].keys()):
            self.access_secret = self.settings["api"]['access_secret']
        self.mystream = None
        self.loop = bot.loop.create_task(self.start_stream())

        
        
    def __unload(self):
        self.mystream.disconnect()

    async def start_stream(self):
        await self.bot.wait_until_ready()
        while self is self.bot.get_cog("Tweets"):
            auth = tw.OAuthHandler(self.consumer_key, self.consumer_secret)
            auth.set_access_token(self.access_token, self.access_secret)
            api = tw.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True, retry_count=10, retry_delay=5, retry_errors=5)
            tweet_list = list(self.settings["accounts"])
            stream_start = TweetListener(api, self.bot)
            if self.mystream is None:
                self.mystream = tw.Stream(api.auth, stream_start, chunk_size=1024, timeout=900.0)
                self.start_stream_loop(tweet_list)
            if not self.mystream.running:
                self.mystream = tw.Stream(api.auth, stream_start, chunk_size=1024, timeout=900.0)
                self.start_stream_loop(tweet_list)
            await asyncio.sleep(300)


    def start_stream_loop(self, tweet_list):
            self.mystream.filter(follow=tweet_list, is_async=True)
        

    async def authenticate(self):
        """Authentifier avec l'API de Twitter"""
        auth = tw.OAuthHandler(self.settings["api"]['consumer_key'], self.settings["api"]['consumer_secret'])
        auth.set_access_token(self.settings["api"]['access_token'], self.settings["api"]['access_secret'])
        return tw.API(auth)

    async def tweet_menu(self, ctx, post_list: list,
                         message: discord.Message=None,
                         page=0, timeout: int=30):
        """logique de contrôle de menu pour cela pris de
           https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py"""
        s = post_list[page]
        created_at = s.created_at
        created_at = created_at.strftime("%d-%m-%Y %H:%M:%S")
        post_url =\
            "https://twitter.com/{}/status/{}".format(s.user.screen_name, s.id)
        desc = "Créé le: {}".format(created_at)
        em = discord.Embed(colour=discord.Colour(value=self.random_colour()),
                           url=post_url,
                           timestamp=s.created_at)
        try:                                
            em.set_author(name=s.user.name, icon_url=s.user.profile_image_url)
        except:
            print(s.user.name + " could not get profile image!")
        # em.add_field(name="Text", value=s.text)
        em.set_footer(text="Retweets: " + str(s.retweet_count))
        if hasattr(s, "extended_entities"):
            em.set_image(url=s.extended_entities["media"][0]["media_url"])
        em.description = s.full_text.replace("&amp;", "\n\n")
        if not message:
            message =\
                await self.bot.send_message(ctx.message.channel, embed=em)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=em)
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
            if page == len(post_list) - 1:
                next_page = 0  # Loop around to the first item
            else:
                next_page = page + 1
            try:
                await self.bot.remove_reaction(message, "➡", ctx.message.author)
            except:
                pass
            return await self.tweet_menu(ctx, post_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(post_list) - 1  # Loop around to the last item
            else:
                next_page = page - 1
            try:
                await self.bot.remove_reaction(message, "⬅", ctx.message.author)
            except:
                pass
            return await self.tweet_menu(ctx, post_list, message=message,
                                         page=next_page, timeout=timeout)
        else:
            return await\
                self.bot.delete_message(message)

    @commands.group(pass_context=True, no_pm=True, name='tweets', aliases=["twitter"])
    async def _tweets(self, ctx):
        """Obtient diverses informations de l'API de Twitter"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @_tweets.command(pass_context=True, name="send")
    @checks.is_owner()
    async def send_tweet(self, ctx, *, message: str):
        """Envoyer un tweet"""
        api = await self.authenticate()
        api.update_status(message)
        await self.bot.send_message(ctx.message.channel, "Tweet envoyé!")

    @_tweets.command(pass_context=True, name="change")
    @checks.is_owner()
    async def change_namet(self, ctx, *, message: str):
        """Change le nom du propriétaire du bot"""
        api = await self.authenticate()
        try:
            api.update_profile(name=message)
        except tw.error.TweepError as e:
            await self.bot.send_message(ctx.message.channel, str(e))
            return
        await self.bot.send_message(ctx.message.channel, "Propriétaire Twitter, nom changé en {}!".format(message))

    def random_colour(self):
        return int(''.join([randchoice('0123456789ABCDEF')for x in range(6)]), 16)

    @_tweets.command(pass_context=True, name="trends")
    async def trends(self, ctx, *, location: str="France"):
        """Obtient les tendances Twitter pour un lieu donné"""
        api = await self.authenticate()
        location_list = api.trends_available()
        country_id = None
        location_names = []
        for locations in location_list:
            location_names.append(locations["name"])
            if location.lower() in locations["name"].lower():
                country_id = locations
                # print(locations)
        if country_id is None:
            await self.bot.say("{} N'est pas un bon emplacement!".format(location))
            return
        trends = api.trends_place(country_id["woeid"])[0]["trends"]
        # print(trends)
        # print(trends)
        em = discord.Embed(colour=discord.Colour(value=self.random_colour()),
                           title=country_id["name"])
        msg = ""
        for trend in trends[:25]:
            # trend = trends[0]["trends"][i]
            if trend["tweet_volume"] is not None:
                msg += "{}. [{}]({}) Volume: {}\n".format(trends.index(trend)+1, trend["name"], trend["url"], trend["tweet_volume"])
            else:
                msg += "{}. [{}]({})\n".format(trends.index(trend)+1, trend["name"], trend["url"])
        em.description = msg[:2000]
        em.timestamp = dt.utcnow()
        await self.bot.send_message(ctx.message.channel, embed=em)


    @_tweets.command(pass_context=True, no_pm=True, name='getuser')
    async def get_user(self, ctx, username: str):
        """Obtenir des informations sur l'utilisateur spécifié"""
        message = ""
        if username is not None:
            api = await self.authenticate()
            user = api.get_user(username)
            url = "https://twitter.com/" + user.screen_name
            emb = discord.Embed(title=user.name,
                                colour=discord.Colour(value=self.random_colour()),
                                url=url,
                                description=user.description)
            emb.set_thumbnail(url=user.profile_image_url)
            emb.add_field(name="Followers", value=user.followers_count)
            emb.add_field(name="Amis", value=user.friends_count)
            if user.verified:
                emb.add_field(name="Verifié", value="Oui")
            else:
                emb.add_field(name="Verifié", value="Non")
            footer = "Créé le " + user.created_at.strftime("%d-%m-%Y %H:%M:%S")
            emb.set_footer(text=footer)
            await self.bot.send_message(ctx.message.channel, embed=emb)
        else:
            message = "Euh oh, une erreur est survenue quelque part!"
            await self.bot.say(message)

    @_tweets.command(pass_context=True, no_pm=True, name='gettweets')
    async def get_tweets(self, ctx, username: str, count: int=1):
        """Récupère le nombre de tweets donné de l'utilisateur voulu"""
        cnt = count
        if count > 25:
            cnt = 25
        if username not in self.settings["accounts"]:
            replies_on = False
        else:
            replies_on = self.settings["accounts"][username]["replies"]

        if username is not None:
            if cnt < 1:
                await self.bot.say("Je ne peux pas faire ça, idiot! Veuillez spécifier un \
                    nombre supérieur ou égal à 1")
                return
            msg_list = []
            api = await self.authenticate()
            try:
                for status in\
                        tw.Cursor(api.user_timeline, id=username, tweet_mode="extended").items(cnt):
                    if status.in_reply_to_screen_name is not None and not replies_on:
                        continue
                    msg_list.append(status)
            except tw.TweepError as e:
                await self.bot.say("Oups! Quelque chose a mal tourné ici. \
                    Le code d'erreur est " + str(e))
                return
            if len(msg_list) > 0:
                await self.tweet_menu(ctx, msg_list, page=0, timeout=30)
            else:
                await self.bot.say("Pas de tweets à afficher!")
        else:
            await self.bot.say("Aucun nom d'utilisateur spécifié!")
            return

    async def on_tweet_error(self, error):
        """Envoyer des messages d'erreur à un canal spécifié par le propriétaire"""
        try:
            if self.settings["error_channel"] is not None:
                channel = self.bot.get_channel(self.settings["error_channel"])
                await self.bot.send_message(channel, error)
        except KeyError:
            self.settings["error_channel"] = None
            dataIO.save_json("data/tweets/settings.json", self.settings)
        return

    
    async def on_tweet_status(self, status):
        """Envoie les tweets dans un canal"""
        # await self.bot.send_message(self.bot.get_channel("321105104931389440"), status.text)
        username = status.user.screen_name
        user_id = str(status.user.id)
        if user_id not in self.settings["accounts"]:
            return
        try:
            if status.in_reply_to_screen_name is not None and not self.settings["accounts"][user_id]["replies"]:
                return
            post_url = "https://twitter.com/{}/status/{}".format(username, status.id)
            em = discord.Embed(colour=discord.Colour(value=self.random_colour()),
                            timestamp=status.created_at)
            try:                                
                em.set_author(name=status.user.name, url=post_url, icon_url=status.user.profile_image_url)
            except:
                print(status.user.name + " could not get profile image!")
            if hasattr(status, "extended_entities"):
                em.set_image(url=status.extended_entities["media"][0]["media_url"])
            if hasattr(status, "extended_tweet"):
                text = status.extended_tweet["full_text"]
                # print(status.extended_tweet)
                if  "media" in status.extended_tweet["entities"]:
                    em.set_image(url=status.extended_tweet["entities"]["media"][0]["media_url"])
            else:
                text = status.text
            em.description = text.replace("&amp;", "\n\n")
            em.set_footer(text="@" + username)
            if text.startswith("RELEASE:") and username == "wikileaks":
                await self.bot.send_message(self.bot.get_channel("365376327278395393"), "<{}>".format(post_url), embed=em)
            for channel in list(self.settings["accounts"][user_id]["channel"]):
                await self.bot.send_message(self.bot.get_channel(channel), "<{}>".format(post_url), embed=em)
            self.settings["accounts"][user_id]["lasttweet"] = status.id
            dataIO.save_json(self.settings_file, self.settings)
        except tw.TweepError as e:
            print("Whoops! Something went wrong here. \
                The error code is " + str(e) + username)
            return
    
    @commands.group(pass_context=True, name='autotweet')
    @checks.admin_or_permissions(manage_channels=True)
    async def _autotweet(self, ctx):
        """Commande permettant de définir des comptes et des canaux pour la publication"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @_autotweet.command(pass_context=True, name="restart")
    async def restart_stream(self, ctx):
        """Redémarre le flux twitter si des problèmes surviennent."""
        self.autotweet_restart()
        await self.bot.send_message(ctx.message.channel, "Redémarrage du flux Twitter.")

    def autotweet_restart(self):
        """Redémarre le flux en déconnectant l'ancien et en le redémarrant avec de nouvelles données"""
        self.mystream.disconnect()
        auth = tw.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_secret)
        api = tw.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True, retry_count=10, retry_delay=5, retry_errors=5)
        tweet_list = list(self.settings["accounts"])
        stream_start = TweetListener(api, self.bot)
        self.mystream = tw.Stream(api.auth, stream_start)
        self.mystream.filter(follow=tweet_list, is_async=True)
    
    @_autotweet.command(pass_context=True, name="replies")
    async def _replies(self, ctx, account, replies):
        """Activer ou désactiver les réponses Twitter pour un compte"""
        account = account.lower()
        channel_list = []
        for user_id in list(self.settings["accounts"]):
            if account == self.settings["accounts"][user_id]["username"].lower():
                channel_list = self.settings["accounts"][user_id]["channel"]
                user = user_id
        if channel_list == []:
            await self.bot.say("{} n'est pas dans ma liste de comptes!".format(account))
            return
        if replies.lower() in ["true", "on"]:
            self.settings["accounts"][user]["replies"] = True
            dataIO.save_json(self.settings_file, self.settings)
            await self.bot.say("Je posterai des réponses pour {} maintenant!".format(account))
        if replies.lower() in ["false", "off"]:
            self.settings["accounts"][user]["replies"] = False
            dataIO.save_json(self.settings_file, self.settings)
            await self.bot.say("Je ne posterai plus les réponses pour {} maintenant!".format(account))

    @_autotweet.command(pass_context=True, name="error")
    @checks.is_owner()
    async def _error(self, ctx, channel:discord.Channel=None):
        """Définit le canal d'erreur pour les erreurs de flux tweets"""
        if not channel:
            channel = ctx.message.channel

        self.settings["error_channel"] = channel.id
        dataIO.save_json(self.settings_file, self.settings)
        await self.bot.send_message(ctx.message.channel, "Envoi de messages d'erreur dans {}".format(channel.mention))


    @_autotweet.command(pass_context=True, name="add")
    async def _add(self, ctx, account, channel:discord.Channel=None):
        """Ajoute un compte twitter au canal spécifié"""
        api = await self.authenticate()
        try:
            for status in tw.Cursor(api.user_timeline, id=account).items(1):
                user_id = str(status.user.id)
                screen_name = status.user.screen_name
                last_id = status.id
        
        except tw.TweepError as e:
            print("Whoops! Something went wrong here. \
                    The error code is " + str(e) + account)
            await self.bot.say("Ce compte n'existe pas! Réessayez")
            return
        if channel is None:
            channel = ctx.message.channel
        added = await self.add_account(channel, user_id, screen_name)
        if added:
            await self.bot.say("{0} Ajouté à {1}!".format(account, channel.mention))
        else:
            await self.bot.say("{} est déjà en train de poster ou n'a pas pu être ajouté à {}".format(account, channel.mention))
        

    async def add_account(self, channel, user_id, screen_name, last_id=0):
        if user_id not in self.settings["accounts"]:
            self.settings["accounts"][user_id] = {"channel" : [], 
                                                  "lasttweet": last_id, 
                                                  "replies": False,
                                                  "username": screen_name}
        if channel.id in self.settings["accounts"][user_id]["channel"]:
            return False
        self.settings["accounts"][user_id]["channel"].append(channel.id)
        dataIO.save_json(self.settings_file, self.settings)
        return True

    @_autotweet.command(pass_context=True, name="list")
    async def _list(self, ctx):
        """Donne les comptes autotweet sur le serveur"""
        account_list = ""
        server = ctx.message.server
        server_channels = [x.id for x in server.channels]
        for account in self.settings["accounts"]:
            for channel_id in self.settings["accounts"][account]["channel"]:
                if channel_id in server_channels:
                    account_list += self.settings["accounts"][account]["username"] + ", "
        if account_list != "":
            embed = discord.Embed(title="Comptes Twitter postés dans {}".format(server.name),
                                  colour=discord.Colour(value=self.random_colour()),
                                  description=account_list[:-2],
                                  timestamp=ctx.message.timestamp)
            embed.set_author(name=server.name, icon_url=server.icon_url)
            await self.bot.send_message(ctx.message.channel, embed=embed)
        else:
            await self.bot.send_message(ctx.message.channel, "Il ne semble pas avoir d'autotweets mis en place ici!")

    @_autotweet.command(pass_context=True, name="addlist")
    async def add_list(self, ctx, owner, list_name, channel:discord.Channel=None):
        """Ajouter une liste complète de twitter à un canal spécifié. La liste doit être publique ou le propriétaire du bot doit la posséder."""
        api = await self.authenticate()
        try:
            cursor = -1
            list_members = []
            member_count = api.get_list(owner_screen_name=owner, slug=list_name).member_count
            print(member_count)
            while len(list_members) < member_count:
                member_list = api.list_members(owner_screen_name=owner, slug=list_name, cursor=cursor)
                for member in member_list[0]:
                    list_members.append(member)
                cursor = member_list[1][-1]
                print("{} membres ajoutés".format(len(member_list[0])))
        except:
            await self.bot.send_message(ctx.message.channel, "Le propriétaire {} et la liste {} ne semblent pas valide!".format(owner, list_name))
            return
        if channel is None:
            channel = ctx.message.channel
        added_accounts = []
        missed_accounts = []
        for member in list_members:
            added = await self.add_account(channel, member.id, member.name)
            if added:
                added_accounts.append(member.name)
            else:
                missed_accounts.append(member.name)
        if len(added_accounts) != 0:
            msg = ", ".join(member for member in added_accounts)
            msg_send = "Ajout des comptes suivants à {}: {}".format(channel.mention, msg)
            for page in pagify(msg_send):
                await self.bot.send_message(ctx.message.channel, page)
        if len(missed_accounts) != 0:
            msg = ", ".join(member for member in missed_accounts)
            msg_send = "Les comptes suivants n'ont pas pu être ajoutés à {}: {}".format(channel.mention, msg)
            for page in pagify(msg_send):
                await self.bot.send_message(ctx.message.channel, page)

    @_autotweet.command(pass_context=True, name="remlist")
    async def rem_list(self, ctx, owner, list_name, channel:discord.Channel=None):
        """Supprimer une liste entière de twitter d'un canal spécifié. La liste doit être publique ou le propriétaire du bot doit la posséder."""
        api = await self.authenticate()
        try:
            cursor = -1
            list_members = []
            member_count = api.get_list(owner_screen_name=owner, slug=list_name).member_count
            print(member_count)
            while len(list_members) < member_count:
                member_list = api.list_members(owner_screen_name=owner, slug=list_name, cursor=cursor)
                for member in member_list[0]:
                    list_members.append(member)
                cursor = member_list[1][-1]
                print("{} members added".format(len(member_list[0])))
        except:
            await self.bot.send_message(ctx.message.channel, "Le propriétaire {} et la liste {} ne semblent pas valide!".format(owner, list_name))
            return
        if channel is None:
            channel = ctx.message.channel
        removed_accounts = []
        missed_accounts = []
        for member in list_members:
            removed = await self.del_account(channel, member.id, member.name)
            if removed:
                removed_accounts.append(member.name)
            else:
                missed_accounts.append(member.name)
        if len(removed_accounts) != 0:
            msg = ", ".join(member for member in removed_accounts)
            msg_send = "Suppression des comptes suivants {}: {}".format(channel.mention, msg)
            for page in pagify(msg_send):
                await self.bot.send_message(ctx.message.channel, page)
        if len(missed_accounts) != 0:
            msg = ", ".join(member for member in missed_accounts)
            msg_send = "Les comptes suivants n'ont pas été ajoutés à {} ou il y a une erreur: {}".format(channel.mention, msg)
            for page in pagify(msg_send):
                await self.bot.send_message(ctx.message.channel, page)
            
        
    async def del_account(self, channel, user_id, screen_name):
        if user_id not in self.settings["accounts"]:
            return False

        if channel.id in self.settings["accounts"][user_id]["channel"]:
            self.settings["accounts"][user_id]["channel"].remove(channel.id)
            if len(self.settings["accounts"][user_id]["channel"]) < 1:
                del self.settings["accounts"][user_id]
        dataIO.save_json(self.settings_file, self.settings)
        return True

    @_autotweet.command(pass_context=True, name="del", aliases=["delete", "rem", "remove"])
    async def _del(self, ctx, account, channel:discord.Channel=None):
        """Supprime un compte twitter pour le canal spécifié"""
        account = account.lower()
        api = await self.authenticate()
        if channel is None:
            channel = ctx.message.channel
        try:
            for status in tw.Cursor(api.user_timeline, id=account).items(1):
                user_id = str(status.user.id)      
        except tw.TweepError as e:
            print("Whoops! Something went wrong here. \
                    The error code is " + str(e) + account)
            await self.bot.say("That account does not exist! Try again")
            return
        removed = await self.del_account(channel, user_id)
        if removed:
            await self.bot.say("{} a été retiré de {}".format(account, channel.mention))
        else:
            await self.bot.say("{0} ne semble pas poster dans {1}!"
                               .format(account, channel.mention))


    @commands.group(pass_context=True, name='tweetset')
    @checks.admin_or_permissions(manage_server=True)
    async def _tweetset(self, ctx):
        """Visitez https://apps.twitter.com pour créer une application"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @_tweetset.command(name='creds')
    @checks.is_owner()
    async def set_creds(self, consumer_key: str, consumer_secret: str, access_token: str, access_secret: str):
        """Sets the access credentials. See [p]help tweetset for instructions on getting these"""
        if consumer_key is not None:
            self.settings["api"]["consumer_key"] = consumer_key
        else:
            await self.bot.say("Aucune clé consumer fournie!")
            return
        if consumer_secret is not None:
            self.settings["api"]["consumer_secret"] = consumer_secret
        else:
            await self.bot.say("Aucune consumer secret fournie!")
            return
        if access_token is not None:
            self.settings["api"]["access_token"] = access_token
        else:
            await self.bot.say("Aucun token d'accès fournie!")
            return
        if access_secret is not None:
            self.settings["api"]["access_secret"] = access_secret
        else:
            await self.bot.say("Aucun access secret fournie!")
            return
        dataIO.save_json(self.settings_file, self.settings)
        await self.bot.say('Fin de la configuration!')

def check_folder():
    if not os.path.exists("data/tweets"):
        print("Creating data/tweets folder")
        os.makedirs("data/tweets")


def check_file():
    data = {"api":{'consumer_key': '', 'consumer_secret': '',
            'access_token': '', 'access_secret': ''}, 'accounts': {}, "error_channel":None}
    f = "data/tweets/settings.json"
    if not dataIO.is_valid_json(f):
        print("Creating default settings.json...")
        dataIO.save_json(f, data)


def setup(bot):
    check_folder()
    check_file()
    if not twInstalled:
        bot.pip_install("tweepy")
        import tweepy as tw
    n = Tweets(bot)
    bot.add_cog(n)
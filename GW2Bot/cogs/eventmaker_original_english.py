from discord.ext import commands
from .utils import checks
from .utils.dataIO import dataIO
from datetime import datetime as dt
from datetime import timedelta, timezone
import asyncio
import aiohttp
import discord
import os
import calendar
import pytz
import re
import collections

# numbs = collections.OrderedDict()
# ⤴ -> join
# ⤵ -> leave
numbs = {
    "next": "➡",
    "back": "⬅",
    "exit": "❌",
    "join": "⤴",
    "leave": "⤵"
}

gametype = {
    "PvE": "🇪",  # E
    "PvP": "🇵",  # P
}

pvp_activity = collections.OrderedDict()
pvp_activity["Casual - PvP"] = "⚒"
pvp_activity["Competitive - PvP"] = "⚔"
pvp_activity["Trials"] = "🥇"
pvp_activity["Other - PvP"] = "🇴"

pve_activity = collections.OrderedDict()
pve_activity["Raid"] = "🇷"       # R
pve_activity["Nightfall"] = "🇳"  # N
pve_activity["Strikes"] = "🇸"    # S
pve_activity["Missions"] = "🇲"   # M
pve_activity["Patrol"] = "🇵"     # P
pve_activity["Other"] = "🇴"      # O

# Define timezones
eastern = pytz.timezone('US/Eastern')
central = pytz.timezone('US/Central')
mountain = pytz.timezone("US/Mountain")
pacific = pytz.timezone('US/Pacific')

""" Cog based heavily off of the cog
    https://github.com/palmtree5/palmtree5-cogs/blob/master/eventmaker/eventmaker.py
    Cog as been altered to cater more towards Destiny.
    Layout of games and messages has also been changed."""


class DestinyLFG():
    """A tool for creating Destiny games inside of Discord. Anyone can
    create an event by default. If a specific role has been
    specified, users must have that role, the server's mod or
    admin role, or be the server owner to create events. Reminders
    will be posted to the configured channel (default: the server's
    default channel), as well as direct messaged to
    everyone who has signed up"""
    def __init__(self, bot):
        self.bot = bot
        self.events = dataIO.load_json(
            os.path.join("data", "destinylfg", "events.json"))
        self.settings = dataIO.load_json(
            os.path.join("data", "destinylfg", "settings.json"))

    async def select_menu(self, ctx, emoji_dict: dict,
                          text: str, timeout: int=30):
        emb = discord.Embed(title=text,
                            color=discord.Colour(0xf1c40f))
        # for name in emoji_dict:
        #     emb.add_field(
        #         name=emoji_dict[name], value=name)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        await self.bot.add_reaction(bot_msg, "⬅")
        await self.bot.add_reaction(bot_msg, "❌")
        await self.bot.add_reaction(bot_msg, "➡")
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌"]
        )
        return bot_msg
        # for name in emoji_dict:
        #     await self.bot.add_reaction(bot_msg, emoji_dict[name])
        # react = await self.bot.wait_for_reaction(
        #     message=bot_msg, user=ctx.message.author, timeout=timeout,
        #     emoji=emoji_dict.values()
        # )
        # if react is None:
        #     for name in emoji_dict:
        #         await self.bot.remove_reaction(bot_msg, emoji_dict[name], self.bot.user)
        #     return None
        # reacts = {v: k for k, v in emoji_dict.items()}
        # return reacts[react.reaction.emoji]

    async def games_menu(self, ctx, event_list: list,
                         message: discord.Message=None,
                         page=0, timeout: int=30):
        """Menu control logic for this taken from
           https://github.com/Lunar-Dust/Dusty-Cogs/blob/master/menu/menu.py """
        emb = event_list[page]
        emb_dict = emb.to_dict()
        if not message:
            message =\
                await self.bot.send_message(ctx.message.channel, embed=emb)
            await self.bot.add_reaction(message, "⬅")
            await self.bot.add_reaction(message, "⤴")
            await self.bot.add_reaction(message, "❌")
            await self.bot.add_reaction(message, "⤵")
            await self.bot.add_reaction(message, "➡")
        else:
            message = await self.bot.edit_message(message, embed=emb)
        react = await self.bot.wait_for_reaction(
            message=message, user=ctx.message.author, timeout=timeout,
            emoji=["➡", "⬅", "❌", "⤴", "⤵"]
        )
        if react is None:
            await self.bot.remove_reaction(message, "⬅", self.bot.user)
            await self.bot.remove_reaction(message, "⤴", self.bot.user)
            await self.bot.remove_reaction(message, "❌", self.bot.user)
            await self.bot.remove_reaction(message, "⤵", self.bot.user)
            await self.bot.remove_reaction(message, "➡", self.bot.user)
            await self.bot.delete_message(message)
            return None
        reacts = {v: k for k, v in numbs.items()}
        react_user = react.user
        react = reacts[react.reaction.emoji]
        if react == "next":
            next_page = 0
            if page == len(event_list) - 1:
                next_page = 0  # Loop around to the first item
            else:
                next_page = page + 1
            return await self.games_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "back":
            next_page = 0
            if page == 0:
                next_page = len(event_list) - 1  # Loop around to the last item
            else:
                next_page = page - 1
            return await self.games_menu(ctx, event_list, message=message,
                                         page=next_page, timeout=timeout)
        elif react == "join":
            await self.bot.say("You got here!!")
            test_server = ctx.message.server
            id_field = next(item for item in emb_dict['fields'] if item["name"] == "Game ID")
            curr_id = int(id_field['value'])
            # for key, value, in emb_dict.items():
            #     print (key, value)
            await self.addplayer(ctx, react_user, curr_id)
            # return await gameslistlfg(ctx)
            return await\
                self.bot.delete_message(message)
        elif react == "leave":
            await self.bot.say("You got here - 2!!")
            test_server = ctx.message.server
            id_field = next(item for item in emb_dict['fields'] if item["name"] == "Game ID")
            curr_id = int(id_field['value'])
            await self.removeplayer(ctx, react_user, curr_id)
            # return await gameslistlfg(ctx)
            return await\
                self.bot.delete_message(message)
        else:
            return await\
                self.bot.delete_message(message)

    @commands.command(pass_context=True)
    async def lfgcreate(self, ctx):
        """Wizard-style destiny lfg creation tool. The event will only be created if
        all information is provided properly
        """
        author = ctx.message.author
        server = ctx.message.server
        await self.bot.delete_message(ctx.message)
        allowed_roles = []
        server_owner = server.owner
        if server.id in self.settings:
            if self.settings[server.id]["role"] is not None:
                specified_role =\
                    [r for r in server.roles if r.id == self.settings[server.id]["role"]][0]
                allowed_roles.append(specified_role)
                allowed_roles.append(self.bot.settings.get_server_mod(server))
                allowed_roles.append(self.bot.settings.get_server_admin(server))

        if len(allowed_roles) > 0 and author != server_owner:
            for role in author.roles:
                if role in allowed_roles:
                    break
            else:
                await self.bot.say("You don't have permission to create events!")
                return

        creation_time = dt.utcnow()
        creation_time = calendar.timegm(creation_time.utctimetuple())
        #####################
        # Get name for game #
        #####################
        bot_msg = await self.bot.say("Enter a name for the event: ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=30)
        if rsp_msg is None:
            await self.bot.say("No name provided!")
            return
        game_name = rsp_msg.content
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)
        #########################
        # Get game descriptions #
        #########################
        # bot_msg = None
        # rsp_msg = None
        bot_msg = await self.bot.say("Enter a description for the event: ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=30)
        if rsp_msg is None:
            await self.bot.say("No description provided!")
            return
        if len(rsp_msg.content) > 750:
            await self.bot.say("Your description is too long!")
            return
        else:
            desc = rsp_msg.content
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)
        #############################
        # Select game activity type #
        #############################
        # bot_msg = None
        # rsp_msg = None
        menu_str = "Select a game type"
        #  react = self.select_menu(ctx, gametype, menu_str, timeout=30)
        emb = discord.Embed(title=menu_str,
                            color=discord.Colour(0xf1c40f))
        for name in gametype:
            emb.add_field(
                name=gametype[name], value=name)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        for name in gametype:
            await self.bot.add_reaction(bot_msg, gametype[name])
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=30,
            emoji=gametype.values()
        )
        if react is None:
            # for name in gametype:
            #     await self.bot.remove_reaction(bot_msg, gametype[name], self.bot.user)
            await self.bot.delete_message(bot_msg)
            await self.bot.say("No game type selected!")
            return None
        reacts = {v: k for k, v in gametype.items()}
        activity_group = reacts[react.reaction.emoji]
        # await self.bot.remove_reaction(bot_msg, gametype[activity_group], react.user)
        await self.bot.delete_message(bot_msg)
        await self.bot.say(reacts[react.reaction.emoji])
        #############################
        # Select specific game type #
        #############################
        # bot_msg = None
        # rsp_msg = None
        menu_str = "Select a game type"
        if activity_group == "PvE":
            emb = discord.Embed(title=menu_str,
                                color=discord.Colour(0x1f8b4c))
            activity_group_dict = pve_activity
        else:
            emb = discord.Embed(title=menu_str,
                                color=discord.Colour(0x992d22))
            activity_group_dict = pvp_activity
        for name in activity_group_dict:
            emb.add_field(
                name=activity_group_dict[name], value=name, inline=False)
        bot_msg = await self.bot.send_message(ctx.message.channel, embed=emb)
        for name in activity_group_dict:
            await self.bot.add_reaction(bot_msg, activity_group_dict[name])
        react = await self.bot.wait_for_reaction(
            message=bot_msg, user=ctx.message.author, timeout=30,
            emoji=activity_group_dict.values()
        )
        if react is None:
            await self.bot.delete_message(bot_msg)
            await self.bot.say("No game type selected!")
            return None
        reacts = {v: k for k, v in activity_group_dict.items()}
        activity_type = reacts[react.reaction.emoji]
        await self.bot.delete_message(bot_msg)
        await self.bot.say(activity_type)
        ##############################
        # Get date and time for game #
        ##############################
        # bot_msg = None
        # rsp_msg = None
        bot_msg = await self.bot.say(
            "Enter the time and date (ex. HH:MM am/pm tz MM/DD): ")
        rsp_msg = await self.bot.wait_for_message(author=author, timeout=45)
        if rsp_msg is None:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("No game time provided!")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            return
        start_time = self.game_time(rsp_msg)
        if start_time is None:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("Something went wrong with parsing the date and time you entered!")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            await self.bot.delete_message(rsp_msg)
            return
        if start_time < creation_time:
            await self.bot.delete_message(bot_msg)
            bot_msg = await self.bot.say("You entered a time in the past!")
            await asyncio.sleep(10)
            await self.bot.delete_message(bot_msg)
            await self.bot.delete_message(rsp_msg)
            return
        await self.bot.delete_message(bot_msg)
        await self.bot.delete_message(rsp_msg)

        new_event = {
            "id": self.settings[server.id]["next_id"],
            "creator": author.id,
            "create_time": creation_time,  # calendar.timegm(creation_time.utctimetuple()),
            "event_name": game_name,
            "activity": activity_type,
            "event_start_time": start_time,
            "description": desc,
            "alert": False,
            "has_started": False,
            "participants": [author.id]
        }
        self.settings[server.id]["next_id"] += 1
        self.events[server.id].append(new_event)
        dataIO.save_json(os.path.join(
            "data", "destinylfg", "settings.json"), self.settings)
        dataIO.save_json(
            os.path.join("data", "destinylfg", "events.json"), self.events)
        emb = discord.Embed(title=new_event["event_name"],
                            description=new_event["description"],
                            color=discord.Colour(0x206694))
        # emb.add_field(name="Created by",
        #               value=discord.utils.get(
        #                   self.bot.get_all_members(),
        #                   id=new_event["creator"]))
        # emb.add_field(name="Created by",
        #               value=author.name)
        emb.set_footer(
            text="Created: " + dt.fromtimestamp(
                new_event["create_time"], central).strftime("%m/%d/%Y %I:%M %p %Z ") +
                        "by " + author.name)
        emb.add_field(
            name="Activity: ", value=new_event["activity"])
        emb.add_field(
            name="Start time: ", value=dt.fromtimestamp(
                new_event["event_start_time"], central).strftime("%I:%M %p %m/%d %Z  "))
        emb.add_field(name="Game ID", value=str(new_event["id"]))
        await self.bot.say(embed=emb)

    @commands.command(pass_context=True)
    async def joinlfg(self, ctx, event_id: int):
        """Join the specified lfg game"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if ctx.message.author.id not in event["participants"]:
                        event["participants"].append(ctx.message.author.id)
                        await self.bot.say("Joined the event!")
                        dataIO.save_json(
                            os.path.join("data", "destinylfg", "events.json"),
                            self.events)
                    else:
                        await self.bot.say("You have already joined that event!")
                else:
                    await self.bot.say("That event has already started!")
                break
        else:
            await self.bot.say("It appears as if that event does not exist!" +
                               "Perhaps it was cancelled or never created?")

    async def addplayer(self, ctx, user, event_id: int):
        """Join the specified lfg game"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if user.id not in event["participants"]:
                        event["participants"].append(user.id)
                        await self.bot.say("Joined the event!")
                        dataIO.save_json(
                            os.path.join("data", "destinylfg", "events.json"),
                            self.events)
                    else:
                        await self.bot.say("You have already joined that event!")
                else:
                    await self.bot.say("That event has already started!")
                break
        else:
            await self.bot.say("It appears as if that event does not exist!" +
                               "Perhaps it was cancelled or never created?")

    @commands.command(pass_context=True)
    async def leavelfg(self, ctx, event_id: int):
        """Leave the specified event"""
        server = ctx.message.server
        author = ctx.message.author
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if author.id in event["participants"]:
                        event["participants"].remove(author.id)
                        await self.bot.say("Removed you from that event!")
                        dataIO.save_json(
                            os.path.join("data", "destinylfg", "events.json"),
                            self.events)
                    else:
                        await self.bot.say(
                            "You aren't signed up for that event!")
                else:
                    await self.bot.say("That event already started!")
                break

    async def removeplayer(self, ctx, user, event_id: int):
        """Leave the specified event"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    if user.id in event["participants"]:
                        event["participants"].remove(user.id)
                        await self.bot.say("Removed you from that event!")
                        dataIO.save_json(
                            os.path.join("data", "destinylfg", "events.json"),
                            self.events)
                    else:
                        await self.bot.say(
                            "You aren't signed up for that event!")
                else:
                    await self.bot.say("That event already started!")
                break

    @commands.command(pass_context=True)
    async def gameslistlfg(self, ctx, *, timezone: str="UTC"):
        """List lfg for this server that have not started yet"""
        server = ctx.message.server
        events = []
        for event in self.events[server.id]:
            if not event["has_started"]:
                et_str = dt.fromtimestamp(
                    event["create_time"], eastern).strftime("%I:%M %p %Z")
                ct_str = dt.fromtimestamp(
                    event["create_time"], central).strftime("%I:%M %p %Z")
                pt_str = dt.fromtimestamp(
                    event["create_time"], pacific).strftime("%m/%d %I:%M %p %Z")
                emb = discord.Embed(title=event["event_name"],
                                    description=event["description"],
                                    color=discord.Colour(0x206694))
                # emb.add_field(name="Created by",
                #               value=(discord.utils.get(
                #                   self.bot.get_all_members(),
                #                   id=event["creator"])).name)
                emb.add_field(
                    name="Activity: ", value=event["activity"])
                # emb.set_footer(
                #     text="Created at (CT) " + dt.fromtimestamp(
                #         event["create_time"], central).strftime("%m/%d/%Y %H:%M"))
                emb.set_footer(
                    text="Start time: " + et_str + ", " + ct_str)
                emb.add_field(
                    name="Start time ", value=pt_str)
                emb.add_field(name="Game ID", value=str(event["id"]))
                player_str = ""
                for user in event["participants"]:
                    target = (discord.utils.get(
                        self.bot.get_all_members(), id=user)).name
                    player_str += target + " "
                # emb.add_field(
                #     name="Participant count", value=str(
                #         len(event["participants"])))
                if player_str == "":
                    player_str = "No Participants"
                emb.add_field(
                    name="Players", value=player_str)
                # emb.add_field(
                #     name="Start time (CT)", value=dt.fromtimestamp(
                #         event["event_start_time"], central).strftime("%m/%d/%Y %H:%M"))
                events.append(emb)
        if len(events) == 0:
            await self.bot.say("No games available to join!")
        else:
            await self.games_menu(ctx, events, message=None, page=0, timeout=30)

    @commands.command(pass_context=True)
    async def whojoinedlfg(self, ctx, event_id: int):
        """List all participants of the destiny lfg"""
        server = ctx.message.server
        for event in self.events[server.id]:
            if event["id"] == event_id:
                if not event["has_started"]:
                    for user in event["participants"]:
                        user_obj = discord.utils.get(
                            self.bot.get_all_members(), id=user)
                        await self.bot.say("{}#{}".format(
                            user_obj.name, user_obj.discriminator))
                else:
                    await self.bot.say("That event has already started!")
                break

    @commands.command(pass_context=True)
    async def cancellfg(self, ctx, event_id: int):
        """Cancels the specified destiny lfg"""
        server = ctx.message.server
        if event_id < self.settings[server.id]["next_id"]:
            to_remove =\
                [event for event in self.events[server.id] if event["id"] == event_id]
            if len(to_remove) == 0:
                await self.bot.say("No event to remove!")
            else:
                self.events[server.id].remove(to_remove[0])
                dataIO.save_json(
                    os.path.join("data", "destinylfg", "events.json"),
                    self.events)
                await self.bot.say("Removed the specified event!")
        else:
            await self.bot.say("I can't remove an event that " +
                               "hasn't been created yet!")

    def game_time(self, msg: discord.Message):
        """Parse the time"""
        # start_time = calendar.timegm(cur_time.utctimetuple())
        content = msg.content
        # CDT = timezone(timedelta(hours=-5))
        try:
            t, ampm, tzone, d = content.split(" ")
            hour, minute = t.split(":")
            month, day = d.split("/")
            # AM or PM
            if ampm.lower() == "pm":
                hour = int(hour) + 12
            # Set Timezone
            tzone = tzone.lower()
            if re.match("p.*t", tzone) is not None:
                tzone = pacific
            elif re.match("e.*t", tzone) is not None:
                tzone = eastern
            elif re.match("c.*t", tzone) is not None:
                tzone = central
            elif re.match("m.*t", tzone) is not None:
                tzone = mountain
            else:
                raise ValueError('Timezone incorrect or not supported')
            #  start_time = dt(2017, int(month), int(day), int(hour), int(minute), tzinfo=tzone)
            start_time = dt(2017, int(month), int(day), int(hour), int(minute))
            start_time = tzone.localize(start_time)
            start_time = calendar.timegm(start_time.utctimetuple())
        except ValueError:
            return None  # issue with the user's input
        return start_time

    @commands.group(pass_context=True)
    @checks.admin_or_permissions(manage_server=True)
    async def game_set(self, ctx):
        """Destiny lfg settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @game_set.command(pass_context=True, name="channel")
    @checks.admin_or_permissions(manage_server=True)
    async def game_set_channel(self, ctx, channel: discord.Channel):
        """Set the channel used for displaying reminders. If 'channel'
        is selected for reminders on event creation, this channel
        will be used. Default: the server's default channel"""
        server = ctx.message.server
        self.settings[server.id]["channel"] = channel.id
        dataIO.save_json(os.path.join("data", "destinylfg", "settings.json"),
                         self.settings)
        await self.bot.say("Channel set to {}".format(channel.mention))

    @game_set.command(pass_context=True, name="role")
    @checks.admin_or_permissions(manage_server=True)
    async def game_set_role(self, ctx, *, role: str=None):
        """Set the role allowed to create events. Default
        is for everyone to be able to create events"""
        server = ctx.message.server
        if role is not None:
            role_obj = [r for r in server.roles if r.name == role][0]
            self.settings[server.id]["role"] = role_obj.id
            dataIO.save_json(
                os.path.join("data", "destinylfg", "settings.json"),
                self.settings)
            await self.bot.say("Role set to {}".format(role))
        else:
            self.settings[server.id]["role"] = None
            dataIO.save_json(
                os.path.join("data", "destinylfg", "settings.json"),
                self.settings)
            await self.bot.say("Role unset!")

    async def check_games(self):
        """Event loop"""
        CHECK_DELAY = 60
        await self.bot.wait_until_ready()
        while self == self.bot.get_cog("DestinyLFG"):
            cur_time = dt.utcnow()
            cur_time = calendar.timegm(cur_time.utctimetuple())
            save = False
            for server in list(self.events.keys()):
                channel = discord.utils.get(self.bot.get_all_channels(),
                                            id=self.settings[server]["channel"])
                for event in self.events[server]:
                    if cur_time >= event["event_start_time"]\
                            and not event["has_started"]:
                        emb = discord.Embed(title=event["event_name"],
                                            description=event["description"],
                                            color=discord.Colour(0x206694))
                        # emb.add_field(name="Created by",
                        #               value=(discord.utils.get(
                        #                   self.bot.get_all_members(),
                        #                   id=event["creator"])).name)
                        emb.add_field(
                            name="Activity: ", value=event["activity"])
                        pt_str = dt.fromtimestamp(
                            event["create_time"], pacific).strftime("%I:%M %p %m/%d %Z")
                        emb.add_field(
                            name="Start time ", value=pt_str)
                        emb.set_footer(
                            text="Created: " +
                            dt.fromtimestamp(
                                event["create_time"], central).strftime(
                                    "%m/%d/%Y %I:%M %p %Z"))
                        emb.add_field(name="Game ID", value=str(event["id"]))
                        # emb.add_field(
                        #     name="Participant count", value=str(
                        #         len(event["participants"])))
                        player_str = ""
                        player_mention_str = "Your game is starting! Join up: "
                        for user in event["participants"]:
                            target = discord.utils.get(
                                self.bot.get_all_members(), id=user)
                            player_str += target.name + " "
                            player_mention_str += target.mention + " "
                        # emb.add_field(
                        #     name="Participant count", value=str(
                        #         len(event["participants"])))
                        if player_mention_str == "Your game is starting! Join up: ":
                            player_mention_str = "Game is starting, but no one has joined"
                        if player_str == "":
                            player_str = "No Participants"
                        emb.add_field(
                            name="Players", value=player_str)
                        try:
                            await self.bot.send_message(channel, player_mention_str)
                            await self.bot.send_message(channel, embed=emb)
                        except discord.Forbidden:
                            pass  # No permissions to send messages
                        for user in event["participants"]:
                            target = discord.utils.get(
                                self.bot.get_all_members(), id=user)
                            await self.bot.send_message(target, embed=emb)
                        event["has_started"] = True
                        save = True
            if save:
                dataIO.save_json(
                    os.path.join("data", "destinylfg", "events.json"),
                    self.events)
            await asyncio.sleep(CHECK_DELAY)

    async def server_join(self, server):
        if server.id not in self.settings:
            self.settings[server.id] = {
                "role": None,
                "next_id": 1,
                "channel": server.id
            }
        if server.id not in self.events:
            self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "destinylfg", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "destinylfg", "settings.json"), self.settings)

    async def server_leave(self, server):
        """Cleanup after leaving server"""
        if server.id in self.events:
            self.events.pop(server.id)
        if server.id in self.settings:
            self.settings.pop(server.id)
        dataIO.save_json(os.path.join("data", "destinylfg", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "destinylfg", "settings.json"), self.settings)

    async def confirm_server_setup(self):
        """Ensures that all servers the bot is in
        have default settings for them. Runs only
        on cog load"""
        for server in list(self.bot.servers):
            if server.id not in self.settings:
                self.settings[server.id] = {
                    "role": None,
                    "next_id": 1,
                    "channel": server.id
                }
                if server.id not in self.events:
                    self.events[server.id] = []
        dataIO.save_json(os.path.join("data", "destinylfg", "events.json"), self.events)
        dataIO.save_json(os.path.join("data", "destinylfg", "settings.json"), self.settings)


def check_folder():
    if not os.path.isdir(os.path.join("data", "destinylfg")):
        print("Creating the destinylfg directory in data")
        os.mkdir(os.path.join("data", "destinylfg"))


def check_file():
    if not dataIO.is_valid_json(os.path.join("data", "destinylfg", "events.json")):
        dataIO.save_json(os.path.join("data", "destinylfg", "events.json"), {})
    if not dataIO.is_valid_json(os.path.join("data", "destinylfg", "settings.json")):
        dataIO.save_json(os.path.join("data", "destinylfg", "settings.json"), {})


def setup(bot):
    check_folder()
    check_file()
    n = DestinyLFG(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.check_games())
    loop.create_task(n.confirm_server_setup())
    bot.add_listener(n.server_join, "on_server_join")
    bot.add_listener(n.server_leave, "on_server_remove")
    bot.add_cog(n)
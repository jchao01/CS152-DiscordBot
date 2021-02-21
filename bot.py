# bot.py
import discord
from discord.ext import commands
from discord.utils import get
import os
import json
import logging
import re
import requests
from report import Report, ReportDatabaseEntry
from review import Review
from uni2ascii import uni2ascii
import globals

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None   
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.reviews = {} # Map from user IDs to the state of their review
        self.perspective_key = key

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')

        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")
        
        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from us 
        if message.author.id == self.user.id:
            return
        
        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_raw_message_edit(self, payload):
        # Message sent in a server
        if "guild_id" in payload.data:
            # Search for the message via guild and channel
            guild = client.get_guild((int)(payload.data["guild_id"]))
            if not guild:
                return
            channel = guild.get_channel((int)(payload.data["channel_id"]))
            if not channel:
                return
            try:
                message = await channel.fetch_message((int)(payload.data["id"]))
            except discord.errors.NotFound:
                return
            
            await self.handle_channel_message(message)
        
        # Message is a DM
        else:
            # Search for the message via channel
            channel = client.get_channel((int)(payload.data["channel_id"]))
            if not channel:
                return
            try:
                message = await channel.fetch_message((int)(payload.data["id"]))
            except discord.errors.NotFound:
                return

            await self.handle_dm(message)

    async def on_raw_reaction_add(self, payload):
        mod_channel = self.mod_channels[payload.guild_id]
        if payload.guild_id in self.mod_channels and payload.emoji.name == "✋" and self.user.id != payload.user_id:
            message = await mod_channel.fetch_message(payload.message_id)
            reaction = get(message.reactions, emoji=payload.emoji.name)
                
            # DM user 
            ticket_message = await mod_channel.fetch_message(payload.message_id)
            id = ticket_message.content.split()[1][1:]
            report = globals.REPORTS_DATABASE[(int)(id)]

            if reaction and reaction.count > globals.NUM_REVIEWERS:
                await message.delete()

            reply = "Report summary for Ticket #" + id + "\n```"
            reply += "Reporting user: " + str(report.reporting_user) + "\n"
            reply += "Reported user: " + str(report.reported_user) + "\n"
            reply += "Message: " + str(report.reported_message.content) + "\n"
            reply += "Category: " + globals.get_catStr(report) + "\n"
            reply += "Additional Info: " + str(report.reported_description) + "```\n"
            reply += "Enter 's' when you're ready to start reviewing."
            await payload.member.send(reply)

            globals.CURRENT_REVIEWERS_DB[payload.user_id] = id

    async def handle_dm(self, message):
        # Translate unicode
        message.content = uni2ascii(message.content)

        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return

        author_id = message.author.id
        responses = []

        # Let the report class handle this message; forward all the messages it returns to us
        if author_id not in globals.CURRENT_REVIEWERS_DB:
        # Only respond to messages if they're part of a reporting flow
            if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
                return

            # If we don't currently have an active report for this user, add one
            if author_id not in self.reports:
                self.reports[author_id] = Report(self)
        
            responses, report = await self.reports[author_id].handle_message(message)
            for r in responses:
                await message.channel.send(r)

            # If the report is complete or cancelled, remove it from our map
            if self.reports[author_id].report_complete():
                self.reports.pop(author_id)
                if report is not None:
                    globals.TICKET_NUM += 1
                    globals.REPORTS_DATABASE[globals.TICKET_NUM] = report
                    await self.handle_report(globals.TICKET_NUM)
        else: # This is a review from a moderator
            # If we don't currently have an active report for this user, add one
            if author_id not in self.reviews and message.content != "s":
                return

            if author_id not in self.reviews:
                self.reviews[author_id] = Review(self)
            
            case_id = globals.CURRENT_REVIEWERS_DB[author_id]
            report = globals.REPORTS_DATABASE[(int)(case_id)]

            responses = await self.reviews[author_id].review_report(message, report, case_id, author_id)
            for r in responses:
                await message.channel.send(r) 

            # If the review is complete or cancelled, remove it from our map
            if self.reviews[author_id].review_complete():
                self.reviews.pop(author_id)
                del globals.CURRENT_REVIEWERS_DB[author_id]
                # Set number of reviewers in globals file
                if (len(globals.REVIEWS_DATABASE[case_id]) >= globals.NUM_REVIEWERS):
                    await self.handle_review(case_id)

    async def handle_review(self, case_id):
        report = globals.REPORTS_DATABASE[(int)(case_id)]
        mod_channel = self.mod_channels[report.reported_message.guild.id]

        decision_code_list = globals.REVIEWS_DATABASE[case_id]
        for i in range(len(decision_code_list)):
            if decision_code_list[i] != decision_code_list[0]:
                decision_code_list[0] = 0
                break

        if decision_code_list[0] > 90:
            await mod_channel.send(f'{report.reported_user} has been absolved. ```Code: {decision_code_list[0]}, Ticket: {case_id}```')
            await report.reporting_user.send('Your report has been processed and we have decided not to take action at this time. Please feel free to DM a moderator if you have further questions.')
        elif 20 <= decision_code_list[0] < 30:
            await report.reported_message.delete()
            await mod_channel.send(f'{report.reported_user} has been (not actually) kicked ```Code: {decision_code_list[0]}, Ticket: {case_id}```')
            await report.reporting_user.send('Your report has been processed - the offending post has been deleted and the offending user has been kicked.')
        elif 10 <= decision_code_list[0] < 20:
            await report.reported_message.delete()
            await mod_channel.send(f'{report.reported_user}\'s offending post has been deleted. ```Code: {decision_code_list[0]}, Ticket: {case_id}```')
            await report.reporting_user.send('Your report has been processed and the offending post has been deleted.')
        elif decision_code_list[0] == 0:
            del globals.REVIEWS_DATABASE[case_id]
            await mod_channel.send(f'```Code: {decision_code_list[0]}, Ticket: {case_id}``` has been reopened. A consensus was not reached.')
            await self.handle_report(case_id)
        
        

    async def handle_report(self, id):
        report = globals.REPORTS_DATABASE[(int)(id)]
        mod_channel = self.mod_channels[report.reported_message.guild.id]
        message = await mod_channel.send(f'Ticket #{id} | {globals.get_catStr(report)}')
        await message.add_reaction('✋')

    async def handle_channel_message(self, message):
        # Translate unicode
        message.content = uni2ascii(message.content)

        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return 
        
        # Forward the message to the mod channel
        mod_channel = self.mod_channels[message.guild.id]

        scores = self.eval_text(message)

        # Determine moderation actions based on scores
        should_delete = False
        should_report = False
        reported_description = ''
        for attr, score in scores.items():
            if score >= globals.AUTO_DELETE_THRESHOLD:
                should_delete = True
            elif score >= globals.AUTO_REPORT_THRESHOLD:
                reported_description += f'\n{attr} score: {score} > auto-report threshold {globals.AUTO_REPORT_THRESHOLD}'
                should_report = True
        
        # Handle moderation actions
        if should_delete:
            await message.author.send('Your message has been flagged by our automatic moderation system and has been deleted.')
            await mod_channel.send(f'Message Auto-Deleted: ```{message.author.name}: "{message.content}"```')
            await message.delete()

        elif should_report:
            await message.author.send('Your message has been flagged by our automatic moderation system and is pending manual review.')
            # Auto detection falls under offensive/harmful/abusive content
            report = ReportDatabaseEntry('ModBot', message.author, message, '1', '5', reported_description)
            # Create report ticket
            globals.TICKET_NUM += 1
            globals.REPORTS_DATABASE[globals.TICKET_NUM] = report
            await self.handle_report(globals.TICKET_NUM)

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'

        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message.content},
            'languages': ['en'],
            'requestedAttributes': {
                                    'SEVERE_TOXICITY': {}, 'PROFANITY': {},
                                    'IDENTITY_ATTACK': {}, 'THREAT': {},
                                    'TOXICITY': {}, 'FLIRTATION': {}
                                },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()

        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]

        return scores
    
    def code_format(self, text):
        return "```" + text + "```"
            
        
client = ModBot(perspective_key)
client.run(discord_token)
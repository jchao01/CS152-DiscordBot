from enum import Enum, auto
import discord
import re
import globals

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    FAKE_SPAM_FRAUD = auto()
    OFFENSIVE_HARMFUL_ABUSIVE = auto()
    OTHER_REASON = auto()
    CATEGORY_COMPLETE = auto()
    DESCRIPTION_COMPLETE = auto()

INCOMPLETE_REPORTS = {}

class ReportDatabaseEntry:
    def __init__(self, reporting_user, reported_user=None, reported_message=None, reported_category=None, reported_subcategory=None, reported_description=None): 
        self.reporting_user = reporting_user
        self.reported_user = reported_user
        self.reported_message = reported_message
        self.reported_category = reported_category
        self.reported_subcategory = reported_subcategory
        self.reported_description = reported_description

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    
    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
    
    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what 
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord. 
        '''

        if message.content == self.CANCEL_KEYWORD:
            del INCOMPLETE_REPORTS[message.author]
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."], None
        
        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            INCOMPLETE_REPORTS[message.author] = ReportDatabaseEntry(message.author)
            self.state = State.AWAITING_MESSAGE
            return [reply], None
        
        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."], None
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."], None
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."], None
            try:
                reported_message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."], None

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_IDENTIFIED
            INCOMPLETE_REPORTS[message.author].reported_user = reported_message.author
            INCOMPLETE_REPORTS[message.author].reported_message = reported_message
            return ["I found this message:", "```" + reported_message.author.name + ": " + reported_message.content + "```", \
                    "Please tell us more about why you're reporting this post.\n 1) I'm not interested in this post.\n 2) It's fake, spam, or fraudulent.\n 3) It's offensive, harmful, or abusive.\n 4) Another reason."], None
        
        if self.state == State.MESSAGE_IDENTIFIED:
            reply = ""
            validReply = False

            if message.content in ["1", "2", "3", "4"]:
                INCOMPLETE_REPORTS[message.author].reported_category = message.content
                validReply = True

            if message.content == "1":
                reply = "Ok, we'll try to show you fewer posts like this (but we can't actually).\n"
                # Doesn't do anything for now
                self.state = State.REPORT_COMPLETE
            elif message.content == "4":
                reply = "Please let us know what type of of abuse/misuse you think this is.\n"
                self.state = State.OTHER_REASON
            elif validReply:
                reply = "Thanks! We just need a little more information. Is it...\n"
                if message.content == "2":
                    reply += "1) Fraudulent\n2) Fake/Misleading\n3) Spam\n4) Impersonation"
                    self.state = State.FAKE_SPAM_FRAUD
                elif message.content == "3":
                    reply += "1) Nudity or Exploitation\n2)Violence, Terrorism, or Incitement\n3) Suicide or Self-Injury\n4) Unauthorized or Illegal Sales\n5) Hate Speech, Harassment, or Bullying"
                    self.state = State.OFFENSIVE_HARMFUL_ABUSIVE

            return [reply], None

        if self.state == State.FAKE_SPAM_FRAUD:
            if message.content in ["1", "2", "3", "4"]:
                INCOMPLETE_REPORTS[message.author].reported_category += "," + message.content
                self.state = State.CATEGORY_COMPLETE
                return ["Alright! Final (optional) step, please share any relevant additional information or type 'skip'and press enter."], None

        if self.state == State.OFFENSIVE_HARMFUL_ABUSIVE:
            if message.content in ["1", "2", "3", "4", "5"]:
                INCOMPLETE_REPORTS[message.author].reported_category += "," + message.content
                self.state = State.CATEGORY_COMPLETE
                return ["Alright! Final (optional) step, please share any relevant additional information or type 'skip'and press enter."], None
        
        if self.state == State.OTHER_REASON:
            INCOMPLETE_REPORTS[message.author].reported_category = "3"
            INCOMPLETE_REPORTS[message.author].reported_subcategory = message.content
            self.state = State.CATEGORY_COMPLETE
            return ["Alright! Final (optional) step, please share any relevant additional information or type 'skip'and press enter."], None

        if self.state == State.CATEGORY_COMPLETE:
            report = INCOMPLETE_REPORTS[message.author]
            if message.content != "skip":
                report.reported_description = message.content
            self.state = State.DESCRIPTION_COMPLETE

            if report.reported_category == "3": 
                category = report.reported_subcategory
            else:
                cat_codes = report.reported_category.split(",")
                # 1 is "I'm not interested in this post"
                cat_codes[0] = str((int)(cat_codes[0]) - 1)
                report.reported_category = cat_codes[0]
                report.reported_subcategory = cat_codes[1]
                category = globals.CATEGORY_CODES[report.reported_category][report.reported_subcategory]

            reply = "Report Summary:\n```"
            reply += "Reporting user: " + str(report.reporting_user) + "\n"
            reply += "Reported user: " + str(report.reported_user) + "\n"
            reply += "Message: " + str(report.reported_message.content) + "\n"
            reply += "Category: " + category + "\n"
            reply += "Additional Info: " + str(report.reported_description) + "```\n"
            reply +="We've received your report, a human will be reviewing it soon. We'll keep you updated via DM. Thank you for helping keep our platform safe!\n\n"
            reply += "We recommend you also review Discord's privacy settings at https://support.discord.com/hc/en-us/articles/217916488-Blocking-Privacy-Settings-"
            reply += "which enable you to block users and prevent unknown server members from direct messaging you."

            del INCOMPLETE_REPORTS[message.author]

            self.state = State.REPORT_COMPLETE
            return [reply], report

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
    


    


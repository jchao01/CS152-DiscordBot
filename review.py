from enum import Enum, auto
import discord
import re
import globals

class State(Enum):
    REVIEW_START = auto()
    CONFIRM_ISSUE = auto()
    CONFIRM_CATEGORY = auto()
    CONFIRM_VIOLATION = auto()
    REVIEW_COMPLETE = auto()

# Fake, Spam, Fraud category shortcodes
FSF_CODES = {"1" : "Fraudulent", "2" : "Fake/Misleading", "3" : "Spam", "4" : "Impersonation"}
# Offensive, Harmful, Abusive category shortcodes
OHA_CODES = {"1" : "Nudity or Exploitation", "2" : "Violence, Terrorism, or Incitement", "3" : "Suicide or Self-Injury", "4" : "Unauthorized or Illegal Sales", "5" : "Hate Speech, Harassment, or Bullying"}

class Review:
    START_KEYWORD = "review"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    
    def __init__(self, client):
        self.state = State.REVIEW_START
        self.client = client
        self.message = None
    
    async def review_report(self, message, report, case_id, reviewer_id):
        '''
        This function makes up the meat of the user-side reviewing flow. It defines how we transition between states and what 
        prompts to offer at each of those states.
        '''
        if self.state == State.REVIEW_START:
            reply =  f'Message: ```{report.reported_message.content}```\n'
            reply += "Is it (remotely) possible that this message violates our policies? Enter 'y' or 'n'" 
            self.state = State.CONFIRM_ISSUE
            return [reply]

        if self.state == State.CONFIRM_ISSUE:
            if message.content == "y":
                reply = f'The reported category was ```{globals.get_catStr(report)}```\n'
                reply += "Is that correct? Enter 'y' or 'n'" 
                self.state = State.CONFIRM_CATEGORY
                return [reply]
            elif message.content == "n":
                reply = "Review complete. Message marked as a non-violation."
                # First review
                if case_id not in globals.REVIEWS_DATABASE:
                    globals.REVIEWS_DATABASE[case_id] = [99]
                else:
                    globals.REVIEWS_DATABASE[case_id].append(99)
                self.state = State.REVIEW_COMPLETE
            return [reply]

        if self.state == State.CONFIRM_CATEGORY:
            # REPLACE WITH A REGEX IN THE FUTURE
            cat_codes = message.content.split(",")
            if cat_codes[0] in ["1", "2"] and cat_codes[1] in ["1", "2", "3", "4", "5"]:
                globals.REPORTS_DATABASE[(int)(case_id)].reported_category = cat_codes[0]
                globals.REPORTS_DATABASE[(int)(case_id)].reported_subcategory = cat_codes[1]
                message.content = "y"

            if message.content == "y":
                report = globals.REPORTS_DATABASE[(int)(case_id)]
                reply = f'```SNIPPET FROM ATTORNEY-APPROVED OFFICIAL CONTENT POLICY REGARDING: {globals.get_catStr(report)}```\n'
                if (report.reported_description != None):
                    reply += f'The victim provided the following additional information: ```{report.reported_description}```\n'
                reply += "Does this post violate the above policy? Enter 'y' or 'n'"
                self.state = State.CONFIRM_VIOLATION
                return [reply]
            elif message.content == "n":
                reply = """
                Category 1: Fake, Spam, or Fraudulent
                    Subcategories:
                    1 : Fraudulent
                    2 : Fake/Misleading
                    3 : Spam
                    4 : Impersonation

                Category 2: Offensive, Hamful, or Abusive
                    Subcategories: 
                    1 : Nudity or Exploitation
                    2 : Violence, Terrorism, or Incitement
                    3 : Suicide or Self-Injury
                    4 : Unauthorized or Illegal Sales 
                    5 : Hate Speech, Harassment, or Bullying\n"""

                reply += "Enter the correct category number followed immediately by the subcategory number. i.e. '1,1' or '2,3'"
                return [reply]

        if self.state == State.CONFIRM_VIOLATION:
            if message.content in ["y", "n"]:
                if message.content == "y":
                    if report.reported_category == "1":
                        code = 10
                    elif report.reported_category == "2":
                        code = 20
                else:
                    code = 99

                if case_id not in globals.REVIEWS_DATABASE:
                    globals.REVIEWS_DATABASE[case_id] = [code]
                else:
                    globals.REVIEWS_DATABASE[case_id].append(code)

                self.state = State.REVIEW_COMPLETE
            return ["Thank you. This review is complete."]

        return []    

    def review_complete(self):
        return self.state == State.REVIEW_COMPLETE
    


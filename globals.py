AUTO_REPORT_THRESHOLD = 0.90
AUTO_DELETE_THRESHOLD = 0.97
TICKET_NUM = 0
# Key: case_id Value: Report
REPORTS_DATABASE = {}
# Key: case_id Value: List of decision codes
REVIEWS_DATABASE = {}
# Key: user_id Value: case_id
CURRENT_REVIEWERS_DB = {}
# Number of reviewers
NUM_REVIEWERS = 1


""" 
Decision Codes:
10 = Fake, spam, fraudulent (delete post)
20 = Offensive, harmful abusive (delete post and kick user - simulate with message)
99 = Innocent post (? restore post ?)
"""

# Key: cat_code Value: Dict
# Key: subcat_code Value: String
# cat_code of 3 indicates a custom category is in subcat
CATEGORY_CODES = {
    "1": {"1" : "Fraudulent", "2" : "Fake/Misleading", "3" : "Spam", "4" : "Impersonation", "5" : "Periscope Auto-Flag"},
    "2": {"1" : "Nudity or Exploitation", "2" : "Violence, Terrorism, or Incitement", "3" : "Suicide or Self-Injury", "4" : "Unauthorized or Illegal Sales", "5" : "Hate Speech, Harassment, or Bullying"}
}

def get_catStr(report):
    if report.reported_category == "3":
        return report.reported_subcategory
    else:
        return CATEGORY_CODES[report.reported_category][report.reported_subcategory]

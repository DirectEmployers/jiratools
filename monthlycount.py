"""
Script for generating monthly stats out of Jira.

"""
from datetime import datetime
from jira.client import JIRA
import secrets

class MonthlyCount:
    def __init__(self):
        # open JIRA API Connection
        options=secrets.options
        housekeeping_auth=secrets.housekeeping_auth
        self.jira = JIRA(options=options, basic_auth=housekeeping_auth)

        for search in secrets.monthlySearches:
            self.get_count(search["jql"],search["label"])

    def get_count(self,query,label):
        """
        Gets and displays issue counts for a given jql query.
        Inputs:
            query: str type. JQL query to run
            label: friendly description of the query to display with the count
        """

        # format date ranges & add to query. Defaults to last month
        start_month = datetime.now().month-1
        if start_month == 0: start_month = 12
        start_month = start_month if start_month > 9 else "0{}".format(start_month)

        end_month = datetime.now().month
        if end_month == 0: end_month = 12
        end_month=end_month if end_month > 9 else "0{}".format(end_month)

        start_year=datetime.now().year
        if start_month==12: start_year = start_year-1
        end_year=datetime.now().year

        start_date = "{}-{}-01".format(start_year,start_month)
        end_date = "{}-{}-01".format(end_year,end_month)
        query = '{} and resolutiondate >= "{}" and resolutiondate < "{}"'.format(query,start_date,end_date)

        # retrieve data. Loop until there are less than 100 results (API limit)
        start = 0
        issues = self.jira.search_issues(query,maxResults=100,startAt=start)
        issue_count = len(issues)
        total = issue_count
        while issue_count==100:
            start += 100
            issues = self.jira.search_issues(query,maxResults=100,startAt=start)
            issue_count = len(issues)
            total += issue_count

        #print the output. Super fancy.
        print ("{}: {}".format(total,label))

MonthlyCount()

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
        start_date = "{}-{}-{}".format(datetime.now().year,datetime.now().month-1,1)
        end_date = "{}-{}-{}".format(datetime.now().year,datetime.now().month,1)
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

from datetime import datetime
from jira.client import JIRA
import secrets
import settings
import statistics

class TimeToTouch:
    def __init__(self):
        # open JIRA API Connection
        options=secrets.options
        housekeeping_auth=secrets.housekeeping_auth
        self.jira = JIRA(options=options, basic_auth=housekeeping_auth)
        self.calculate_touch_time("Sales-Engineering")

    def calculate_touch_time(self,team):
        """
        Calculates Mean and Median time to touch for tasks.

        Inputs:
            :team:  Jira Group Name for the team

        Returns: Console Print

        """
        # init the issue container
        issues = []

        # get the issues. Can only do it 100 at a time, so loop-the-loop
        jql = self.jira.filter(secrets.time_to_touch_filters[team]).jql
        start=1
        max=100
        tempIssues = self.get_issues(jql,start,max)
        issues = tempIssues
        start=start+max
        while len(tempIssues)==max:
            tempIssues = self.get_issues(jql,start,max)
            start=start+max
            issues = issues+tempIssues

        # init the list to contain the touch time
        touchList = []
        # get user list
        userList = self.get_group_members(team)
        for issue in issues:
            createdDate=datetime.strptime(
                issue.fields.created.split(".")[0],
                "%Y-%m-%dT%H:%M:%S"
                )
            ticketLog = issue.changelog.histories # get the ticket changelog

            # init the dict that will contain the ticket key, author, and time to touch
            touchDict = {}
            touchDict["issue"]=issue.key

            logCount = ticketLog.__len__()
            i = logCount-1
            countItem=False

            # walk the log list until oldest entry found.
            # The list is newest first, so start in the back
            #print(userList)
            while i >= 0:
                author = ticketLog.__getitem__(i).author
                #print(author.accountId)

                if author.accountId in userList:
                    seTouchDate=datetime.strptime(
                        ticketLog.__getitem__(i).created.split(".")[0],
                        "%Y-%m-%dT%H:%M:%S"
                        )
                    seTouch = seTouchDate-createdDate
                    seTouchHours = round(seTouch.total_seconds()/60/60,2)
                    #print(author)
                    touchDict["User"]=author
                    touchDict["touchTime"]=seTouchHours
                    countItem=True
                    i=-1
                else:
                    i=i-1

            if(countItem):
                # Ignore issues where noone from the user list is in the log
                # This happens when a ticket is handled by someone outside the team
                touchList.append(touchDict)

        touchTimeData = []
        for touch in touchList:
            touchTimeData.append(touch["touchTime"])

        # builds the output strings and prints to console.
        touchAverage = round(statistics.mean(touchTimeData),2)
        touchAverage = self.min_hr_switch(touchAverage)
        touchMedian = round(statistics.median(touchTimeData),2)
        touchMedian = self.min_hr_switch(touchMedian)
        print("{}: ".format(team))
        print("    Average: {}".format(touchAverage))
        print("    Median: {}".format(touchMedian))
        print()
        

    def get_issues(self,jql,start,max):
        """
        Returns issues found using a jira filter.  Supports max and start values as the
        Jira API has a hard limit on results and requires looped queries to get all issues
        when the count is higher than that.

        Inputs:
            :jql:   the dict key for the filter in settings
            :start: Start point for the query (to support followup requests)
            :max:   Max results. Usually 100, based on API limits

        Returns:
            :issues:    Jira Issues object

        """
        result = self.jira.search_issues(
            jql,
            startAt=start,
            expand="changelog",
            maxResults=max
            )
        return result

    def min_hr_switch(self,touchTime):
        """
        Switches between hours and minutes for readability
        Inputs:
            :touchTime: Hour measurement. Float

        Returns:
            :touchTime: String statement of time interval

        """
        if touchTime < 1:
            touchTime = str(touchTime*60) + " Minutes"
        else:
            touchTime = str(touchTime) + " Hours"
        return touchTime

    def get_group_members(self, group_name):
        """
        Returns the members of a group as a list
        """
        group = self.jira.groups(query=group_name)[0]
        members = self.jira.group_members(group)
        return members

TimeToTouch()

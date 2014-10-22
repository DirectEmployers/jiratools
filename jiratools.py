# This script shows how to connect to a JIRA instance with a
# username and password over HTTP BASIC authentication.

from datetime import datetime
from jira.client import JIRA
import logging
import random
import secrets


class Housekeeping():
    """
    This class is the container for all automated Jira functions performed
    by the Housekeeping agent.
    
    """ 
    def __init__(self):
        # open JIRA API Connection
        self.jira = JIRA(options=secrets.options, 
                            basic_auth=secrets.housekeeping_auth) 
    
        # commands to run
        self.content_acquisition_auto_qc()
        self.random_auto_assign()

    def content_acquisition_auto_qc(self):
        # Get some issues
        issues = self.jira.search_issues(
            'project=INDEXREP and status=Merged and updated<="-30m"')

        # Iterate on the issues
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = '[~%s], this issue is ready for QC.' % reporter
            self.jira.transition_issue(issue.key,'771')
            self.jira.add_comment(issue.key, message)

    def random_auto_assign(self):
        ca_group = self.jira.groups(
            query='content-acquisition'
            )['groups'][0]['name']
        members = self.jira.group_members(ca_group)
        issues = self.jira.search_issues(
            'project=INDEXREP and (assignee=EMPTY OR assignee=housekeeping) and \
             status in (open,reopened)')
        
        # iterate over the issues and randomly assign them to a user 
        for issue in issues:
            ran_dev = random.choice(members.keys())
            reporter = issue.fields.reporter.key
            self.jira.assign_issue(issue=issue,assignee=ran_dev)
            message = ("[~%s], this issue has been automically assigned "
                "to [~%s].") % (reporter,ran_dev)
            self.jira.add_comment(issue.key, message)


Housekeeping()

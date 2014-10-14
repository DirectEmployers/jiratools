# This script shows how to connect to a JIRA instance with a
# username and password over HTTP BASIC authentication.

import logging
from jira.client import JIRA
from datetime import datetime
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

    def content_acquisition_auto_qc(self):
        # Get some issues
        issues = self.jira.search_issues('project=INDEXREP and status=Merged and updated<="-30m"')

        # Iterate on the issues
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = '[~%s], this issue is ready for QC.' % reporter
            self.jira.transition_issue(issue.key,'771')
            self.jira.add_comment(issue.key, message)

Housekeeping()

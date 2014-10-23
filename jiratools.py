"""
Jira Housekeeping (c)2014 DirectEmployers Association. See README 
for license info.

"""
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
        # class variables
        self.ac_label =  u'auto-close-24-hours'
        # open JIRA API Connection
        self.jira = JIRA(options=secrets.options, 
                            basic_auth=secrets.housekeeping_auth) 
    
        # commands to run
        self.content_acquisition_auto_qc()
        self.random_auto_assign()
        self.remind_reporter_to_close()
        self.close_resolved()
        self.clear_auto_close_label()

    def content_acquisition_auto_qc(self):
        """
        Takes INDEXREP issues that have been Merged for 30+ minutes and 
        transitions them to Quality Control. It then adds a comment that
        tags the reporter to inform them that the issue is ready for review.

        """
        issues = self.jira.search_issues(
            'project=INDEXREP and status=Merged and updated<="-30m"')

        for issue in issues:
            reporter = issue.fields.reporter.key
            message = '[~%s], this issue is ready for QC.' % reporter
            """ 
            771 is the transition ID spedific to this step for this project.
            Anything more generic will need to parse the transitions list.
            """
            self.jira.transition_issue(issue.key,'771')
            self.jira.add_comment(issue.key, message)

    def random_auto_assign(self):
        """
        Looks up new INDEXREP issues with an empty assignee and non-agent
        reporter and assigns them randomly to a developer in the 
        content-acquisition user group.

        """
        ca_group = self.jira.groups(
            query='content-acquisition'
            )['groups'][0]['name']
        members = self.jira.group_members(ca_group)
        issues = self.jira.search_issues(
            'project=INDEXREP and (assignee=EMPTY OR assignee=housekeeping) and \
             status in (open,reopened) and reporter != contentagent and \
             summary !~ "free index"')
       
        for issue in issues:
            ran_dev = random.choice(members.keys())
            reporter = issue.fields.reporter.key
            self.jira.assign_issue(issue=issue,assignee=ran_dev)
            message = ("[~%s], this issue has been automically assigned "
                "to [~%s].") % (reporter,ran_dev)
            self.jira.add_comment(issue.key, message)

    def remind_reporter_to_close(self):
        """
        Comments on all non-closed resolved issues that are 13 days without a
        change. Notifies the reporter it will be closed in 24 hours and adds a
        label to the issue that is used as a lookup key by the close method.

        """
        issues = self.jira.search_issues(
            'resolution != EMPTY AND \
            status not in (closed, "Quality Control", Reopened, Merged, open) \
            AND updated <= -13d')
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = (
                "[~%s], this issue has been resolved for 13 days. It will be "
                "closed automatically in 24 hours.") % reporter
            self.jira.add_comment(issue.key,message)
            issue.fields.labels.append(self.ac_label)
            issue.update(fields={"labels": issue.fields.labels})

    def close_resolved(self):
        """
        Looks up all issues labeled for auto-closing that have not been updated
        in 24 hours and closes them.

        """
        issues = self.jira.search_issues(
            'resolution != EMPTY AND \
            status not in (closed, "Quality Control", Reopened, Merged, open) \
            AND updated <= -24h \
            AND labels in (auto-close-24-hours)')
        for issue in issues:
            trans = self.jira.transitions(issue)
            for tran in trans:
                if tran['name'].lower()=="close":
                    self.jira.transition_issue(issue,tran['id'])

    def clear_auto_close_label(self):
        """
        Clears the auto-close label from issues that have been re-opened
        since the auto-close reminder was posted.

        """
        issues = self.jira.search_issues(
            'status in ("Quality Control", Reopened, Merged, open) \
            AND labels in (auto-close-24-hours)')
        for issue in issues:
            label_list =  issue.fields.labels
            label_list.remove(self.ac_label)
            issue.update(fields={"labels": label_list})
                    

Housekeeping()

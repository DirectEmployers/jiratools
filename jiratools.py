"""
Jira Housekeeping (c)2014 DirectEmployers Association. See README 
for license info.

Reference for using the jira client:
http://jira-python.readthedocs.org/en/latest/

"""
from datetime import datetime
from jira.client import JIRA
import logging
import operator
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
        self.auto_assign()
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

    def auto_assign(self):
        """
        Looks up new INDEXREP issues with an empty assignee and non-agent
        reporter and assigns them to the user in the content-acquisition user 
        group with the fewest assigned contect-acquistion tickets. 

        """
        ca_group = self.jira.groups(
            query='content-acquisition'
            )['groups'][0]['name']
        members = self.jira.group_members(ca_group)
        issues = self.jira.search_issues(
            'project=INDEXREP and (assignee=EMPTY OR assignee=housekeeping) and \
             status in (open,reopened) and reporter != contentagent and \
             summary !~ "free index"')

        assigned_issues = self.jira.search_issues(
            'project=INDEXREP and status in (open,reopened)')
        
        member_count = {}

        for member in members:
            member_count[member]=0

        for issue in assigned_issues:
            if issue.fields.assignee:
                assignee = issue.fields.assignee.key
            else:
                assignee = None
            if assignee in members and not self.label_contains(issue,"wait"):
                member_count[assignee] = member_count[assignee]+1
        
        member_count_sorted = sorted(member_count.items(), 
            key=operator.itemgetter(1))
        username = str(member_count_sorted[0][0])
        
        for issue in issues:
            reporter = issue.fields.reporter.key
            watch_list = self.toggle_watchers("remove",issue)
            self.jira.assign_issue(issue=issue,assignee=username)
            message = ("[~%s], this issue has been automically assigned "
                "to [~%s].") % (reporter,username)
            self.jira.add_comment(issue.key, message)
            self.toggle_watchers("add",issue,watch_list)
 

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
            watch_list = self.toggle_watchers("remove",issue)
            self.jira.add_comment(issue.key,message)
            issue.fields.labels.append(self.ac_label)
            issue.update(fields={"labels": issue.fields.labels})
            self.toggle_watchers("add",issue, watch_list)

    def close_resolved(self):
        """
        Looks up all issues labeled for auto-closing that have not been updated
        in 24 hours and closes them.

        """
        issues = self.jira.search_issues(
            'resolution != EMPTY AND \
            status not in (closed, "Quality Control", Reopened, Merged, open, \
            passed,staged) \
            AND updated <= -24h \
            AND labels in (auto-close-24-hours)')
        for issue in issues:
            trans = self.jira.transitions(issue)
            for tran in trans:
                if 'close' in tran['name'].lower():
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
            watch_list = self.toggle_watchers("remove",issue)
            label_list.remove(self.ac_label)
            issue.update(fields={"labels": label_list})
            self.toggle_watchers("add",issue, watch_list)


    def toggle_watchers(self,action,issue,watch_list=[]):
        """
        Internal method that either adds or removes the watchers of an issue. If
        it removes them,it returns a list of users that were removed. If it 
        adds, it returns an updated list of watchers.
        
        Inputs:
        :action: String "add"|"remove". The action to take
        :issue:  Issue whose watchers list is being modified
        :watch_list: list of users. Optional for remove. Required for add.
        
        Returns:
        :issue_watcher: List of users who are or were watching the issue.
        
        """
        if action=="remove":
            issue_watchers = self.jira.watchers(issue).watchers
            for issue_watcher in issue_watchers:
                self.jira.remove_watcher(issue,issue_watcher.name)
        else:
            for old_watcher in watch_list:
                self.jira.add_watcher(issue,old_watcher.name)
            issue_watchers = self.jira.watchers(issue).watchers
        return issue_watchers

    def label_contains(self,issue,search_string):
        """
        Internal method that searches the labels of an issue for a given string
        value. It allows filtering that is roughly "labels ~ 'string'", which
        is not supported by JQL.

        Inputs:
        :issue: Jira issue object that is being checked
        :search_string: the string value being checked for

        Returns:
        :found: True if search_string exists in any label. Default is False.

        """
        found = False
        for label in issue.fields.labels:
            if search_string in label:
                found = True
        return found

Housekeeping()

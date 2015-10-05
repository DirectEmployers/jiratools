"""
Jira Housekeeping (c)2014 DirectEmployers Association. See README 
for license info.

Reference for using the jira client:
http://pythonhosted.org/jira/

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
        #self.content_acquisition_auto_qc()
        #self.auto_assign()
        #self.remind_reporter_to_close()
        #self.close_resolved()
        #self.clear_auto_close_label()

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
    
    def handle_audited_tickets(self):
        #return True #keep it running. remove once the method runs
        # look up failed audits. We only care about failed ADT tickets.
        issues = self.jira.search_issues(
            'project=ADT and status="Failed Audit"')
        # generate new indexrep ticket
        for issue in issues:            
            link_list = [issue.key,]
            for link in issue.fields.issuelinks:
                link_list.append(link.outwardIssue.key)            
            indexrep_summary = issue.fields.summary
            original_ticket = issue.fields.summary.split("(")[1].split(")")[0]
            indexrep_summary = indexrep_summary.replace("compliance audit - ","")
            indexrep_summary = ' %s - Failed Audit' % (indexrep_summary)
            message = 'This issue failed audit. Please review %s and make any necessary corrections.' % original_ticket            
            watcher_list = [issue.fields.assignee.key,]
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)
            watcher_list = set(watcher_list)
            reporter = issue.fields.reporter.key
            print indexrep_summary
            print issue
            print link_list
            print reporter
            print message
            print watcher_list
            #new_issue = self.make_new_issue("INDEXREP",qa_auditor,reporter,adt_summary,message,watcher_list,[link_back])
            #original_assignee = issue.fields.assignee.key
            #generate list of linked issues. Include this issue
            #capture the report
            
        # link it to ADT and original INDEXREP ticket
        # make it unassigned
        # transfer watchers of original INDEXREP ticket, but not the assignee from the ADT ticket
        # reporter should be same as ADT
        # assignee unassigned
        # comment on the ADT ticket with the new ticket value and the original INDEXREP issue
        # close the ADT ticket
    
    def content_acquisition_3day_audit(self):
        """
        TAKES INDEXREP issues that have been resolved for 72 hours and creates
        a new ticket in AUDIT, closes the INDEXREP ticket, and then assigns it
        to the audit user specified in the self.qa_auditor role.
        841
        
        """
        # get all the INDERXREP issues
        issues = self.jira.search_issues(
            'project=TEST and status=Resolved')# and resolutiondate<="-72h"')
        qa_members = self.get_group_members("issue audits")
        if len(qa_members)==1:
            qa_auditor=qa_members.keys()[0]
        else:
            # for now, throw an error. Later, assign to user with fewer ADT tickets
            # this will also mean turning the code in auto_assign into a method (DRY)
            return "Error: There is more than possible auditor"
        
        # cycle through them and create a new ADT ticket for each        
        for issue in issues:
            link_back = issue.key
            adt_summary = 'compliance audit - %s (%s)' % (issue.fields.summary,link_back)
            message = '[~%s], this issue is ready to audit.' % qa_auditor
            watcher_list = []
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)
            reporter = issue.fields.reporter.key
            original_assignee = issue.fields.assignee.key
            # debug info for dev feedback
            #print 'Key: %s \n    Summary: %s \n    Message: %s \n    Watchers of ADT: %s, \n    Reporter: %s \n    Assignee: %s \n    Original Assignee: %s \n------------------\n' % (link_back, adt_summary, message, watcher_list, reporter, qa_auditor, original_assignee)
            #print 'Actions: \n    - %s issue will be closed\n    - a new ADT ticket will be created\n    - The ADT ticket will be assigned\n    - Watchers will include all original watchers + original assignee' % (link_back)
            #print '    - reporter will be original reporter'
            #print '    - new ADT will link to %s' % link_back
            #print '+++++++++++++++++++++++++'            
           
            # make the audit ticket
            new_issue = self.make_new_issue("ADT",qa_auditor,reporter,adt_summary,message,watcher_list,[link_back])
           
            # close the INDEXREP ticket
            close_me = self.close_issue(link_back)
            print close_me
            
            # add comment to indexrep ticket
            link_back_comment = "This issue has been closed. The audit ticket is %s" % new_adt
            self.jira.add_comment(link_back, link_back_comment)
        
    def make_new_issue(self,project,issue_assignee,issue_reporter,summary,description="",watchers=[],links=[],issuetype="Task"):
        """
        Creates a new issue with the given parameters.
        Inputs:
        *REQUIRED*
            :project:   the jirs project key in which to create the issue
            :issue_assignee:    user name who the issue will be assigned to
            :issue_reporter:    user name of the issue report
            :summary:   string value of the issue summary field
            *OPTIONAL*
            :description: Issue description. Defaults to empty string
            :watchers: list of user names to add as issue watchers
            :link:  list of issue keys to link to the issue as "Related To"
            :issuetype: the type of issue to create. Defaults to type.
        Returns: Jira Issue Object
        
        """
        issue_dict = {
            'project':{'key':project},
            'summary': adt_summary,
            'issuetype': {'name':issuetype},
            'description':description,        
            }
        new_issue = self.jira.create_issue(fields=audit_dict)
        
        # assign the audit tick to auditor
        new_issue.update(assignee={'name':,issue_assignee})
        new_issue.update(reporter={'name':issue_reporter})
        
        # add watchers to audit ticket (reporter, assignee, wacthers from indexrep ticket)
        for watcher in watchers:
            self.jira.add_watcher(new_issue,watcher)
        
        # link the audit ticket back to indexrep ticket
        for link in links:
            self.jira.create_issue_link('Relates',new_issue,link)
            
        return new_issue
            
    # method to transistion audit ticket    
    def get_group_members(self, group_name):
        """
        Returns the members of a 
        """
        group = self.jira.groups(
            query=group_name
            )['groups'][0]['name']
        members = self.jira.group_members(group)
        return members
        
    def auto_assign(self):
        """
        Looks up new INDEXREP issues with an empty assignee and non-agent
        reporter and assigns them to the user in the content-acquisition user 
        group with the fewest assigned contect-acquistion tickets. 

        """
        #ca_group = self.jira.groups(
        #    query='content-acquisition'
        #    )['groups'][0]['name']
        #members = self.jira.group_members(ca_group)        
        members = self.get_group_members('content-acquisition')
        
        issues = self.jira.search_issues(
            'project=INDEXREP and (assignee=EMPTY OR assignee=housekeeping) and \
            status in (open,reopened) and reporter != contentagent and \
            (summary !~ "free index" OR (summary ~ "free index" and summary ~ "renew"))')

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
            close_me = self.close_issue(issue)
            
    def close_issue(self, issue):
        """
        Closes the issue passed to it.
        Inputs: Issue: the issue object to close
        Returs: True|False
        
        """
        trans = self.jira.transitions(issue)
        success_flag = False
        for tran in trans:
            if 'close' in tran['name'].lower():
                self.jira.transition_issue(issue,tran['id'])
                success_flag = True
        return success_flag
                
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
        True|False  True if search_string exists in any label.

        """
        return any(search_string in label for label in issue.fields.labels)        

Housekeeping()

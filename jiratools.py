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
        self.content_acquisition_auto_qc()
        self.auto_assign()
        self.remind_reporter_to_close()
        self.close_resolved() 
        self.clear_auto_close_label()
        self.resolved_issue_audit()
        self.handle_audited_tickets()
        
        
    def content_acquisition_auto_qc(self):
        """
        Takes INDEXREP issues that have been Merged for 30+ minutes and 
        transitions them to Quality Control. It then adds a comment that
        tags the reporter to inform them that the issue is ready for review.

        """
        #23700 grabs CA tickets merged 30+ minute ago
        jql_query = self.jira.filter("23700").jql
        issues = self.jira.search_issues(jql_query)
        
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = '[~%s], this issue is ready for QC.' % reporter
            """ 
            771 is the transition ID spedific to this step for this project.
            Anything more generic will need to parse the transitions list.
            """
            tran_id = self.get_transition_id(issue,"qc")
            self.jira.transition_issue(issue.key,tran_id)
            self.jira.add_comment(issue.key, message)
    
    def handle_audited_tickets(self):
        """
        Handles audit tickets that are failed. Closed tickets are ignored. Failed 
        tickets trigger the creation of a new ticket in the same project as the 
        original ticket.
        
        Inputs: None
        Returns: None
        
        """
        issues = self.jira.search_issues(   # get all the ADT issues
            'project=ADT and status="Failed Audit"')
        
        # For each failed issue, generate a new work ticket then close this one
        for issue in issues:
            #BUID
            adt_buid=issue.fields.customfield_10502
            #WCID
            adt_wcid=issue.fields.customfield_10501
            #oldBUID
            adt_old_buid=issue.fields.customfield_13100
            #oldWCID
            adt_old_wcid=issue.fields.customfield_13101
            #Indexing Type
            adt_indexing_type=issue.fields.customfield_10500
            #comments
            adt_comments = []
            for comment in self.jira.comments(issue):
                node = {
                    'body':self.jira.comment(issue,comment).body,
                    'author': self.jira.comment(issue,comment).author.key
                }
                adt_comments.append(node)
                        
            link_list = [issue.key,] # first linked ticket should be this audit ticket
            for link in issue.fields.issuelinks: # grab the rest of links
                try:
                    link_list.append(link.outwardIssue.key)
                except AttributeError:
                    pass
            
            # capture original ticket and project. If it can't be found, default to INDEXREP as the project
            try:
                original_ticket = issue.fields.summary.split("[")[1].split("]")[0]
                original_project = original_ticket.split("-")[0]
            except IndexError:
                original_ticket = ""
                original_project="INDEXREP"
            
            # build the new summary by parsing the audit summary
            indexrep_summary = issue.fields.summary #build the summary
            indexrep_summary = indexrep_summary.replace("compliance audit - ","")
            indexrep_summary = indexrep_summary.split("[")[0]
            indexrep_summary = ' %s - Failed Audit' % (indexrep_summary)
            
            # Build the issue description
            message = 'This issue failed audit. Please review %s and make any \
                necessary corrections.' % original_ticket

            # Construct the watcher list and de-dupe it
            watcher_list = [issue.fields.assignee.key,]
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)
            watcher_list = set(watcher_list)
            
            # get the reporter (reporter is preserved from audit to issue)
            reporter = issue.fields.reporter.key
            
            # Generate the new issue, then close the audit ticket.    
            new_issue = self.make_new_issue(original_project,"EMPTY",reporter,
                                                indexrep_summary,message,
                                                watcher_list,link_list,adt_buid,                                                
                                                adt_wcid,adt_old_buid,adt_old_wcid,
                                                adt_indexing_type,adt_comments)            
            close_me = self.close_issue(issue.key)
                        
    
    def resolved_issue_audit(self):
        """
        TAKES issues that have been resolved from specified projectsfor a set 
        interval and creates a new ticket in AUDIT, closes the INDEXREP ticket, 
        and then assigns it to the audit user specified in the self.qa_auditor role.
        
        Inputs: None
        Returns:    Error message or Nothing
        
        """
        # get all the issues from projects in the audit list
        issue_query = self.jira.filter("23800").jql
        issues = self.jira.search_issues(issue_query) 
        
        #build a list of all users in the MS & MD groups
        member_svc = self.get_group_members("member-services")            
        member_dev = self.get_group_members("membership-development")
        member_all = []
        for user in member_svc:
            member_all.append(user) #only need the user names, not the meta data
        for user in member_dev:
            member_all.append(user)
        member_all = set(member_all) #de-dupe
        
        
        # cycle through them and create a new ADT ticket for each 
        for issue in issues:
            # capture issue fields
            ind_buid=issue.fields.customfield_10502 #BUID            
            ind_wcid=issue.fields.customfield_10501 #WCID            
            ind_old_buid=issue.fields.customfield_13100 #oldBUID            
            ind_old_wcid=issue.fields.customfield_13101 #oldWCID            
            ind_indexing_type=issue.fields.customfield_10500 #Indexing Type            
            reporter = issue.fields.reporter.key #Reporter
            
            link_list = [issue.key,]
            for link in issue.fields.issuelinks: # grab the rest of links
                try:
                    link_list.append(link.outwardIssue.key)
                except AttributeError:
                    pass
            # build the new ticket summary based on the issue being audited
            # [ISSUE=123] is used to preserve the original issue key. Replace any brackets with () 
            # to prevent read errors later.
            adt_summary = issue.fields.summary.replace("[","(").replace("]",")")
            adt_summary = 'compliance audit - %s [%s]' % (adt_summary,issue.key)
            
            # check reporter to see if special consideration is needed
            # if reporter is not MS or MD, or it's a new member, assign to audit lead.
            new_member_setup = self.check_for_text(issue,["new member setup","setup member"])
            assigned_audit_tasks_query = self.jira.filter("24922").jql
            if reporter not in member_all or new_member_setup:
                qa_auditor = self.user_with_fewest_issues('issue audits lead', 
                                                      assigned_audit_tasks_query)
            else:
                # get the users who can be assigned audit tickets, then select the 
                # one with fewest assigned tickets                
                qa_auditor = self.user_with_fewest_issues('issue audits', 
                                                          assigned_audit_tasks_query)
            
            # build the description
            message = '[~%s], issue %s is ready to audit.' % (qa_auditor, issue.key)
            
            #build the watcher list, including original reporter and assignee of the audited ticket
            watcher_list = []
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)
            
            try:
                original_assignee = issue.fields.assignee.key
            except AttributeError:
                original_assignee="EMPTY"      
            
            # make the audit ticket
            new_issue = self.make_new_issue("ADT",qa_auditor,reporter,
                adt_summary,message,watcher_list,link_list,ind_buid,
                ind_wcid,ind_old_buid,ind_old_wcid,ind_indexing_type)
           
            # close the INDEXREP ticket
            close_me = self.close_issue(issue.key)
            
            # add comment to indexrep ticket
            link_back_comment = "This issue has been closed. The audit ticket is %s" % new_issue
            self.jira.add_comment(issue.key, link_back_comment)
            
        
    def make_new_issue(self,project,issue_assignee,issue_reporter,summary,
                                      description="",watchers=[],links=[],
                                      buid="",wcid="",old_buid="",old_wcid="",
                                      indexing_type="",comments=[],
                                      issuetype="Task"):
        """
        Creates a new issue with the given parameters.
        Inputs:
        *REQUIRED*
            :project:   the jira project key in which to create the issue
            :issue_assignee:    user name who the issue will be assigned to
            :issue_reporter:    user name of the issue report
            :summary:   string value of the issue summary field
            *OPTIONAL*
            :description: Issue description. Defaults to empty string
            :watchers: list of user names to add as issue watchers
            :link:  list of issue keys to link to the issue as "Related To"
            :issuetype: the type of issue to create. Defaults to type.
            :buid: business unit - custom field 10502
            :wcid: wrapping company id - custom field 10501
            :old_buid: old business unit - custom field 13100
            :old_wcid: old wrapping company id - custom field 13101
            :indexing_type: the indexing type - custom field 10500
            :comments: list dictionaries of comments and authors to auto add.
        Returns: Jira Issue Object
        
        """
        issue_dict = {
            'project':{'key':project},
            'summary': summary,
            'issuetype': {'name':issuetype},
            'description':description,        
            }
        new_issue = self.jira.create_issue(fields=issue_dict)
        
        # assign the audit tick to auditor
        new_issue.update(assignee={'name':issue_assignee})
        new_issue.update(reporter={'name':issue_reporter})
        
        # add watchers to audit ticket (reporter, assignee, wacthers from indexrep ticket)
        for watcher in watchers:
            self.jira.add_watcher(new_issue,watcher)
        
        # link the audit ticket back to indexrep ticket
        for link in links:
            self.jira.create_issue_link('Relates',new_issue,link)
        
        # add custom field values if set
        if buid:
            new_issue.update(fields={'customfield_10502':buid})
        if wcid:
            new_issue.update(fields={'customfield_10501':wcid})
        if indexing_type:
            new_issue.update(fields={'customfield_10500':{'value':indexing_type.value}})
        if old_buid:
            new_issue.update(fields={'customfield_13100':old_buid})
        if old_wcid:
            new_issue.update(fields={'customfield_13101':old_wcid})
        
        # add comments
        quoted_comments = ""
        for comment in comments:
            quoted_comments = "%s[~%s] Said:{quote}%s{quote}\\\ \\\ " % (quoted_comments,comment['author'],comment['body'])
            
        if quoted_comments:
            quoted_comments = "Comments from the parent issue:\\\ %s" % quoted_comments
            self.jira.add_comment(new_issue,quoted_comments)
            
        return new_issue
            
    # method to transistion audit ticket    
    def get_group_members(self, group_name):
        """
        Returns the members of a group as a list
        """
        group = self.jira.groups(
            query=group_name
            )['groups'][0]['name']
        members = self.jira.group_members(group)
        return members
    
    def auto_assign(self,project="INDEXREP"):
        """
        Looks up new INDEXREP issues with an empty assignee and non-agent
        reporter and assigns them to the user in the content-acquisition user 
        group with the fewest assigned contect-acquistion tickets. 

        """       
        
        # filter 20702 returns member INDEXREP issues that need to auto assigned
        jql_query = self.jira.filter("20702").jql        
        mem_issues = self.jira.search_issues(jql_query)
        
        #filter 23300 returns free indexing requests (FCA & select INDEXREP tix)
        jql_query = self.jira.filter("23300").jql
        free_issues = self.jira.search_issues(jql_query)
        
        issues = mem_issues+free_issues
        
        #filter 23401 returns non-resolved assigned Member issues
        member_assigned_issues_query = self.jira.filter("23400").jql
        
        #filter 23401 returns non-resolved assigned Free Indexing issues
        free_assigned_issues_query = self.jira.filter("23401").jql
        
        def _assign(issue,username):
            """
            Private method for assigning an issue.
            Inputs:
            issue: issue to assign
            username: person to assign the issue
            
            """
            reporter = issue.fields.reporter.key
            watch_list = self.toggle_watchers("remove",issue)
            self.jira.assign_issue(issue=issue,assignee=username)
            message = ("[~%s], this issue has been automically assigned "
                "to [~%s].") % (reporter,username)
            self.jira.add_comment(issue.key, message)
            self.toggle_watchers("add",issue,watch_list)
        
        # count and assign member tickets
        for issue in mem_issues:            
            username = self.user_with_fewest_issues('content-acquisition', 
                                                    member_assigned_issues_query)
            _assign(issue,username)            
        
        # count and assign free tickets
        for issue in free_issues:
            username = self.user_with_fewest_issues('content-acquisition', 
                                                    free_assigned_issues_query)
            _assign(issue,username)
        
         
            
        
    def remind_reporter_to_close(self):
        """
        Comments on all non-closed resolved issues that are 13 days without a
        change. Notifies the reporter it will be closed in 24 hours and adds a
        label to the issue that is used as a lookup key by the close method.

        """
        issues = self.jira.search_issues(
            'resolution != EMPTY AND \
            status not in (closed, "Quality Control", Reopened, Merged, open) \
            AND updated <= -13d and project not in (INDEXREP)')
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
        in 24 hours and closes them. Ignores INDEXREP so as to not interfere
        with the auditing process.

        """
        issues = self.jira.search_issues(
            'resolution != EMPTY AND \
            status not in (closed, "Quality Control", Reopened, Merged, open, \
            passed,staged) AND project not in (INDEXREP) \
            AND updated <= -24h \
            AND labels in (auto-close-24-hours)')
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = (
                "[~%s], this issue has closed automatically.") % reporter
            close_me = self.close_issue(issue)
            self.jira.add_comment(issue.key,message)
    
    def get_transition_id(self,issue,key):
        """
        Finds the transition id for an issue given a specific search string.
        Inputs: 
            key: search string
            issue: jira issue
        Returns: transition id or False
        
        """
        trans = self.jira.transitions(issue)
        tran_id = False
        for tran in trans:
            tran_name = tran['name'].lower()
            if key in tran_name:
                tran_id = tran['id']
        return tran_id
    
    def close_issue(self, issue):
        """
        Closes the issue passed to it with a resolution of fixed.
        Inputs: Issue: the issue object to close
        Returns: True|False
        
        """
        trans = self.jira.transitions(issue)
        success_flag = False
        tran_id = self.get_transition_id(issue,"close")
        if not tran_id:
            tran_id = self.get_transition_id(issue,"complete")
        
        if tran_id:
            try:
                self.jira.transition_issue(issue,tran_id,
                                           {'resolution':{'id':'1'}})
            #some close transitions don't have a resolution screen
            except: #open ended, but the JIRAError exception is broken.
                self.jira.transition_issue(issue,tran_id)
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
  
  
    def check_for_text(self,issue,text_list):        
        """
        Internal method that searches the summary and description of an issue for 
        a given list of strings.

        Inputs:
        :issue: Jira issue object that is being checked
        :text_list: strings to checked for

        Returns:
        True|False  True if any of the values in text_list exist.

        """
        string_exists = False
        if issue.fields.summary:
            summary = issue.fields.summary
        else:
            summary = ""
            
        if issue.fields.description:
            description = issue.fields.description
        else:
            description = ""
            
        for text in text_list:
            if text in summary or text in description:
                string_exists = True
        
        return string_exists
         
    
    def user_with_fewest_issues(self,group,query):
        """
        Given a query, return the username of the use with the fewest assigned
        issues in the result set.
        
        Inputs:
        group: the group of users for which to count issues.
        query: the issues to lookup. Should be a JQL string.
        
        """
        members = self.get_group_members(group)
        
        issues = self.jira.search_issues(query,maxResults=1000)
        
        member_count = {}

        for member in members:
            member_count[member]=0

        # perform the count anew for each ticket
        for issue in issues:
            if issue.fields.assignee:
                assignee = issue.fields.assignee.key
            else:
                assignee = None
            if assignee in members and not self.label_contains(issue,"wait"):
                member_count[assignee] = member_count[assignee]+1
                
        #sort the list so that the user with the lowest count is first
        member_count_sorted = sorted(member_count.items(), 
            key=operator.itemgetter(1))
        # return the username of the user
        return str(member_count_sorted[0][0]) 

Housekeeping()

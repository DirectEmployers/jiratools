"""
Jira Housekeeping copyright 2014-2019 DirectEmployers Association. See README
for license info.

Reference for using the jira client:
http://pythonhosted.org/jira/

"""
from datetime import datetime
from jira.client import JIRA
import logging
import operator
import secrets
import settings

class Housekeeping:
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
        self.requeue_free_indexing()
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
        # get CA tickets merged 30+ minute ago
        issues = self.get_issues("auto_qc")

        for issue in issues:
            reporter = issue.fields.reporter.key
            message = '[~{}], this issue is ready for QC.'.format(reporter)
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
            indexrep_summary = ' {} - Failed Audit'.format(indexrep_summary)

            # Build the issue description
            message = 'This issue failed audit. Please review {} and make any necessary corrections.'.format(original_ticket)

            # Construct the watcher list and de-dupe it
            watcher_list = [issue.fields.assignee.key,]
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)
            watcher_list = set(watcher_list)

            # get the reporter (reporter is preserved from audit to issue)
            reporter = issue.fields.reporter.key

            # Generate the new issue, then close the audit ticket.
            new_issue = self.make_new_issue(original_project,"",reporter,
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
        issues = self.get_issues("audit_list")

        #build a list of all users in the MS & MD groups
        member_svc = self.get_group_members("member-services")
        member_dev = self.get_group_members("membership-development")
        member_aud = self.get_group_members("issue audits")
        member_all = []
        for user in member_svc:
            member_all.append(user) #only need the user names, not the meta data
        for user in member_dev:
            member_all.append(user)
        for user in member_aud:
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
            adt_summary = 'compliance audit - {} [{}]'.format(adt_summary,issue.key)

            # check reporter to see if special consideration is needed
            # if reporter is not MS or MD, or it's a new member, assign to audit lead.
            new_member_setup = self.check_for_text(issue,
                                                   settings.member_setup_strs)
            assigned_audit_tasks_query = self.get_issues("assigned_audits",True)
            if reporter not in member_all or new_member_setup:
                qa_auditor = self.user_with_fewest_issues('issue audits lead',
                                                      assigned_audit_tasks_query,
                                                      [reporter])
            else:
                # get the users who can be assigned audit tickets, then select the
                # one with fewest assigned tickets
                qa_auditor = self.user_with_fewest_issues('issue audits',
                                                          assigned_audit_tasks_query,
                                                          [reporter])

            # build the description
            message = '[~{}], issue {} is ready to audit.'.format(qa_auditor, issue.key)

            #build the watcher list, including original reporter and assignee of the audited ticket
            watcher_list = []
            for w in self.jira.watchers(issue).watchers:
                watcher_list.append(w.key)

            try:
                original_assignee = issue.fields.assignee.key
            except AttributeError:
                original_assignee=""

            # make the audit ticket
            new_issue = self.make_new_issue("ADT",qa_auditor,reporter,
                adt_summary,message,watcher_list,link_list,ind_buid,
                ind_wcid,ind_old_buid,ind_old_wcid,ind_indexing_type)

            # close the INDEXREP ticket
            close_me = self.close_issue(issue.key)

            # add comment to indexrep ticket
            link_back_comment = "This issue has been closed. The audit ticket is {}".format(new_issue)
            self.jira.add_comment(issue.key, link_back_comment)


    def requeue_free_indexing(self):
        """
        Takes a list of old FCA tickets, and clears the assignee fields in order to
        allow it to be reassigned.

        Inputs: None
        Returns: Nothing

        """
        # get issues that are stale and need reassigned
        issues = self.get_issues("stale_free")

        # itirate issues and set assignee to empty. This will allow
        # auto assignment to set the assignee.
        for issue in issues:
            #check for wait in label
            wait_label = self.label_contains(issue,"wait")
            # if no wait label, clear the assignee so it can be re-autoassigned
            if (not wait_label):
                issue.update(assignee={'name':""})


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
            try:
                self.jira.add_watcher(new_issue,watcher)
            except:
                pass

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
            quoted_comments = "{}[~{}] Said:{}{}{}\\\ \\\ ".format(
                                                                quoted_comments,
                                                                comment['author'],
                                                                "{quote}",
                                                                comment['body'],
                                                                "{quote}")

        if quoted_comments:
            quoted_comments = "Comments from the parent issue:\\\ {}".format(quoted_comments)
            self.jira.add_comment(new_issue,quoted_comments)

        return new_issue

    # method to transistion audit ticket
    def get_group_members(self, group_name):
        """
        Returns the members of a group as a list
        """
        group = self.jira.groups(query=group_name)[0]
        members = self.jira.group_members(group)
        return members

    def auto_assign(self,project="INDEXREP"):
        """
        Looks up new INDEXREP issues with an empty assignee and non-agent
        reporter and assigns them to the user in the content-acquisition user
        group with the fewest assigned contect-acquistion tickets.

        """
        # get member INDEXREP issues that need to auto assigned
        mem_issues = self.get_issues("member_auto_assign")
        # get free indexing requests
        free_issues = self.get_issues("free_auto_assign")
        # get unassigned member engagement issues
        mer_issues = self.get_issues("mer_auto_assign")
        # get unassigned sales engineering issues
        se_issues = self.get_issues("se_auto_assign")

        # get non-resolved assigned Member issues
        member_assigned_issues_query = self.get_issues("member_assigned_issues",True)
        # get non-resolved assigned Free Indexing issues
        free_assigned_issues_query = self.get_issues("free_assigned_issues",True)
        # get non-resolved member enagement issues
        mer_assigned_issues_query = self.get_issues("mer_assigned_issues",True)
        # get non-resolved sales engineering issues
        se_assigned_issues_query = self.get_issues("se_assigned_issues",True)

        def _assign(issue,username):
            """
            Private method for assigning an issue.
            Inputs:
            issue: issue to assign
            username: person to assign the issue

            """
            reporter = issue.fields.reporter.key
            self.jira.assign_issue(issue=issue,assignee=username)

            message = ("[~{}], this issue has been automically assigned to [~{}].").format(reporter,username)
            self.jira.add_comment(issue.key, message)

        auto_assign_dicts = [
            {
                "issue_list": mem_issues,
                "assigned_list": member_assigned_issues_query,
                "assignee_group": "content-acquisition",
            },
            {
                "issue_list": free_issues,
                "assigned_list": free_assigned_issues_query,
                "assignee_group": "content-acquisition-free",
            },
            {
                "issue_list": mer_issues,
                "assigned_list": mer_assigned_issues_query,
                "assignee_group": "mer-assignees",
                "watch_list":"mer-auto-watch",
            },
            {
                "issue_list": se_issues,
                "assigned_list": se_assigned_issues_query,
                "assignee_group": "se-assignees",
            }]

        for auto_assign_dict in auto_assign_dicts:
            for issue in auto_assign_dict["issue_list"]:
                username = self.user_with_fewest_issues(auto_assign_dict["assignee_group"],
                                                        auto_assign_dict["assigned_list"])


                if (auto_assign_dict["issue_list"]==mem_issues or
                    auto_assign_dict["issue_list"]==free_issues):
                    # check if the indexing type is already set. If so, do nothing.
                    if issue.fields.customfield_10500 == None:
                        # default to member indexing for issues in mem_issues
                        if auto_assign_dict["issue_list"]==mem_issues:
                            issue.update({"customfield_10500":{"id":"10103"}})

                        elif auto_assign_dict["issue_list"]==free_issues:
                            free_index_mem = self.get_group_members("free-index-default")
                            # set the indexing type to free if the reporter is in the list
                            # of users who default to free
                            if issue.fields.reporter.key in free_index_mem:
                                issue.update({"customfield_10500":{"id":"10100"}}) #free
                            else: #default is member otherwise
                                issue.update({"customfield_10500":{"id":"10103"}})

                # if the dict object has a watch list item, add default watchers
                if "watch_list" in auto_assign_dict:
                    watchers = self.get_group_members(auto_assign_dict["watch_list"])
                    self.toggle_watchers("add",issue,watchers)

                _assign(issue,username)


    def remind_reporter_to_close(self):
        """
        Comments on all non-closed resolved issues that are 13 days without a
        change. Notifies the reporter it will be closed in 24 hours and adds a
        label to the issue that is used as a lookup key by the close method.

        """
        issues = self.get_issues("remind_close_issues")
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = "[~{}], this issue has been resolved for 13 days. It will be closed automatically in 24 hours.".format(reporter)
            self.bot_comment(issue,message)
            self.toggle_label(issue,secrets.ac_label,"add")

    def close_resolved(self):
        """
        Looks up all issues labeled for auto-closing that have not been updated
        in 24 hours and closes them. Ignores INDEXREP so as to not interfere
        with the auditing process.

        """
        issues = self.get_issues("auto_close_issues")
        for issue in issues:
            reporter = issue.fields.reporter.key
            message = "[~{}], this issue has closed automatically.".format(reporter)
            print("closed {}".format(issue))
            self.close_issue(issue)
            self.bot_comment(issue,message)

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
        watch_list = self.toggle_watchers("remove",issue)
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

        watch_list = self.toggle_watchers("add",issue,watch_list)
        return success_flag

    def clear_auto_close_label(self):
        """
        Clears the auto-close label from issues that have been re-opened
        since the auto-close reminder was posted.

        """
        issues = self.get_issues("autoclose_label")
        for issue in issues:
            self.toggle_label(issue,secrets.ac_label,"remove")

    def bot_comment(self,issue,message):
        """
        Comments on a ticket without notifying watchers.
        Inputs: Issue: the issue object to close
        Message: What to comment

        """
        watch_list = self.toggle_watchers("remove",issue)
        self.jira.add_comment(issue.key,message)
        self.toggle_watchers("add",issue, watch_list)

    def toggle_label(self,issue,label,action):
        """
        Adds a label without notifying watchers.
        Inputs: issue: the issue object to label
                label: the label to add/remove
                action: add/remove (str)

        """
        watch_list = self.toggle_watchers("remove",issue)
        label_list =  issue.fields.labels
        if action=="add":
            label_list.append(label)
        else:
            label_list.remove(label)
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
                # watch list can be inconsensent when returned by the jira api
                # same issue in the add loop
                try:
                    self.jira.remove_watcher(issue,issue_watcher.name)
                except AttributeError:
                    self.jira.add_watcher(issue,old_watcher)
        else:
            for old_watcher in watch_list:
                try:
                    self.jira.add_watcher(issue,old_watcher.name)
                except AttributeError:
                    self.jira.add_watcher(issue,old_watcher)
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
        a given list of strings. Match is non-case sensative, and converts
        everything to lower case before checking for a match.

        Inputs:
        :issue: Jira issue object that is being checked
        :text_list: strings to checked for

        Returns:
        True|False  True if any of the values in text_list exist.

        """
        string_exists = False
        if issue.fields.summary:
            summary = issue.fields.summary.lower()
        else:
            summary = ""

        if issue.fields.description:
            description = issue.fields.description.lower()
        else:
            description = ""

        for text in text_list:
            text = text.lower()
            if text in summary or text in description:
                string_exists = True

        return string_exists


    def user_with_fewest_issues(self,group,query,blacklist=[]):
        """
        Given a query, return the username of the use with the fewest assigned
        issues in the result set.

        Inputs:
        group: the group of users for which to count issues.
        query: the issues to lookup. Should be a JQL string.
        blacklist: (optional) list of inelligible users

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

        # prevent assignment to a user in the blacklist, so long as there are
        # at least 2 available users
        while (str(member_count_sorted[0][0]) in blacklist and
            len(member_count_sorted)>1):
            del member_count_sorted[0]

        # return the username of the user
        return str(member_count_sorted[0][0])


    def get_issues(self,filter_key,return_jql=False):
        """
        Returns issues found using a jira filter.

        Inputs:
            :filter_key:    the dict key for the filter in settings
            :return_jql:    flag to return JQL instead on issues

        Returns:
            :issues:    Jira Issues object (default) or JQL string

        """
        filter_id = secrets.jira_filters[filter_key]
        jql_query = self.jira.filter(filter_id).jql
        if return_jql:
            # some functionality needs the JQL instead of an issue list
            # notably the method self.user_with_fewest_issues
            return jql_query
        else:
            issues = self.jira.search_issues(jql_query)
            return issues


Housekeeping()

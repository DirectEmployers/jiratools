from jira.client import JIRA
import secrets

class JiraTasks():        
    def __init__(self):
        self.jira = JIRA(options=secrets.options, 
                         basic_auth=secrets.housekeeping_auth)
        
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
                self.jira.add_watcher(issue,old_watcher)
            issue_watchers = self.jira.watchers(issue).watchers
        return issue_watchers
"""Engineering Analytics — Multi-schema, individual Properties, cross-system linking.

Patterns: Multi-schema sources (4 organizational domains), many concepts with
simple identity, Property for all scalar attributes (not bundled Relationships),
Relationship for cross-system links (GitHub <-> project management),
prefixed concept names for collision avoidance.
Best practices: Property for scalars, Relationship for concept-to-concept links.
"""
from relationalai.semantics import Model, Date, DateTime, Float, Integer, String

model = Model("Engineering Analytics")

# ── Source Tables (multi-schema: 4 domains, 30+ tables) ──────────
class Sources:
    class eng_analytics:
        class github:
            ci_jobs = model.Table("ENG_ANALYTICS.GITHUB.CI_JOBS")
            ci_runners = model.Table("ENG_ANALYTICS.GITHUB.CI_RUNNERS")
            commit = model.Table("ENG_ANALYTICS.GITHUB.COMMIT")
            deployment = model.Table("ENG_ANALYTICS.GITHUB.DEPLOYMENT")
            issue = model.Table("ENG_ANALYTICS.GITHUB.ISSUE")
            pull_request = model.Table("ENG_ANALYTICS.GITHUB.PULL_REQUEST")
            pull_request_review = model.Table("ENG_ANALYTICS.GITHUB.PULL_REQUEST_REVIEW")
            repository = model.Table("ENG_ANALYTICS.GITHUB.REPOSITORY")
            team = model.Table("ENG_ANALYTICS.GITHUB.TEAM")
            user = model.Table("ENG_ANALYTICS.GITHUB.USER")
            workflow = model.Table("ENG_ANALYTICS.GITHUB.WORKFLOW")
            workflow_run = model.Table("ENG_ANALYTICS.GITHUB.WORKFLOW_RUN")
        class project_mgmt:
            board = model.Table("ENG_ANALYTICS.PROJECT_MGMT.BOARD")
            comment = model.Table("ENG_ANALYTICS.PROJECT_MGMT.COMMENT")
            component = model.Table("ENG_ANALYTICS.PROJECT_MGMT.COMPONENT")
            epic = model.Table("ENG_ANALYTICS.PROJECT_MGMT.EPIC")
            issue = model.Table("ENG_ANALYTICS.PROJECT_MGMT.ISSUE")
            project = model.Table("ENG_ANALYTICS.PROJECT_MGMT.PROJECT")
            sprint = model.Table("ENG_ANALYTICS.PROJECT_MGMT.SPRINT")
            user = model.Table("ENG_ANALYTICS.PROJECT_MGMT.USER")
            version = model.Table("ENG_ANALYTICS.PROJECT_MGMT.VERSION")
            worklog = model.Table("ENG_ANALYTICS.PROJECT_MGMT.WORKLOG")
        class infra:
            consumer_account = model.Table("ENG_ANALYTICS.INFRA.CONSUMER_ACCOUNT")
            engine = model.Table("ENG_ANALYTICS.INFRA.ENGINE")
            transaction = model.Table("ENG_ANALYTICS.INFRA.TRANSACTION")
        class platform_api:
            data_streams = model.Table("ENG_ANALYTICS.PLATFORM_API.DATA_STREAMS")
            databases = model.Table("ENG_ANALYTICS.PLATFORM_API.DATABASES")
            engines = model.Table("ENG_ANALYTICS.PLATFORM_API.ENGINES")
            transactions = model.Table("ENG_ANALYTICS.PLATFORM_API.TRANSACTIONS")

# ── Concepts ─────────────────────────────────────────────────────
# GitHub domain
GitHubUser = model.Concept("GitHubUser", identify_by={"id": Integer})
model.define(GitHubUser.new(id=Sources.eng_analytics.github.user.id))

GitHubRepository = model.Concept("GitHubRepository", identify_by={"id": Integer})
model.define(GitHubRepository.new(id=Sources.eng_analytics.github.repository.id))

GitHubPullRequest = model.Concept("GitHubPullRequest", identify_by={"id": Integer})
model.define(GitHubPullRequest.new(id=Sources.eng_analytics.github.pull_request.id))

GitHubCommit = model.Concept("GitHubCommit", identify_by={"sha": String})
model.define(GitHubCommit.new(sha=Sources.eng_analytics.github.commit.sha))

GitHubWorkflow = model.Concept("GitHubWorkflow", identify_by={"id": Integer})
model.define(GitHubWorkflow.new(id=Sources.eng_analytics.github.workflow.id))

GitHubCIJob = model.Concept("GitHubCIJob", identify_by={"job_id": Integer})
model.define(GitHubCIJob.new(job_id=Sources.eng_analytics.github.ci_jobs.job_id))

GitHubTeam = model.Concept("GitHubTeam", identify_by={"id": Integer})
model.define(GitHubTeam.new(id=Sources.eng_analytics.github.team.id))

# Project management domain
PMProject = model.Concept("PMProject", identify_by={"id": Integer})
model.define(PMProject.new(id=Sources.eng_analytics.project_mgmt.project.id))

PMIssue = model.Concept("PMIssue", identify_by={"id": Integer})
model.define(PMIssue.new(id=Sources.eng_analytics.project_mgmt.issue.id))

PMSprint = model.Concept("PMSprint", identify_by={"id": Integer})
model.define(PMSprint.new(id=Sources.eng_analytics.project_mgmt.sprint.id))

PMEpic = model.Concept("PMEpic", identify_by={"id": Integer})
model.define(PMEpic.new(id=Sources.eng_analytics.project_mgmt.epic.id))

PMUser = model.Concept("PMUser", identify_by={"id": String})
model.define(PMUser.new(id=Sources.eng_analytics.project_mgmt.user.id))

# ── Properties (scalar attributes — individual, not bundled) ─────
# GitHub user
GitHubUser.login = model.Property(f"{GitHubUser} has {String:login}")
GitHubUser.name = model.Property(f"{GitHubUser} has {String:name}")
GitHubUser.company = model.Property(f"{GitHubUser} has {String:company}")
GitHubUser.bio = model.Property(f"{GitHubUser} has {String:bio}")
GitHubUser.location = model.Property(f"{GitHubUser} has {String:location}")
GitHubUser.is_site_admin = model.Relationship(f"{GitHubUser} is site admin")
GitHubUser.created_at = model.Property(f"{GitHubUser} has {Integer:created_at}")

# GitHub repository
GitHubRepository.name = model.Property(f"{GitHubRepository} has {String:name}")
GitHubRepository.full_name = model.Property(f"{GitHubRepository} has {String:full_name}")
GitHubRepository.is_private = model.Relationship(f"{GitHubRepository} is private")
GitHubRepository.description = model.Property(f"{GitHubRepository} has {String:description}")
GitHubRepository.primary_language = model.Property(f"{GitHubRepository} has {String:primary_language}")
GitHubRepository.fork_count = model.Property(f"{GitHubRepository} has {Integer:fork_count}")
GitHubRepository.watcher_count = model.Property(f"{GitHubRepository} has {Integer:watcher_count}")
GitHubRepository.is_archived = model.Relationship(f"{GitHubRepository} is archived")
GitHubRepository.default_branch = model.Property(f"{GitHubRepository} has {String:default_branch}")

# GitHub pull request
GitHubPullRequest.created_at = model.Property(f"{GitHubPullRequest} has {Integer:created_at}")
GitHubPullRequest.updated_at = model.Property(f"{GitHubPullRequest} has {Integer:updated_at}")
GitHubPullRequest.closed_at = model.Property(f"{GitHubPullRequest} has {Integer:closed_at}")
GitHubPullRequest.merge_commit_sha = model.Property(f"{GitHubPullRequest} has {String:merge_commit_sha}")
GitHubPullRequest.is_draft = model.Relationship(f"{GitHubPullRequest} is draft")
GitHubPullRequest.head_ref = model.Property(f"{GitHubPullRequest} has {String:head_ref}")
GitHubPullRequest.base_ref = model.Property(f"{GitHubPullRequest} has {String:base_ref}")

# GitHub commit
GitHubCommit.message = model.Property(f"{GitHubCommit} has {String:message}")
GitHubCommit.timestamp = model.Property(f"{GitHubCommit} has {Integer:timestamp}")
GitHubCommit.committer_name = model.Property(f"{GitHubCommit} has {String:committer_name}")
GitHubCommit.author_name = model.Property(f"{GitHubCommit} has {String:author_name}")

# PM issue
PMIssue.summary = model.Property(f"{PMIssue} has {String:summary}")
PMIssue.description = model.Property(f"{PMIssue} has {String:description}")
PMIssue.original_estimate = model.Property(f"{PMIssue} has {Float:original_estimate}")
PMIssue.remaining_estimate = model.Property(f"{PMIssue} has {Float:remaining_estimate}")
PMIssue.time_spent = model.Property(f"{PMIssue} has {Float:time_spent}")

# PM sprint
PMSprint.start_date = model.Property(f"{PMSprint} has {Integer:start_date}")
PMSprint.end_date = model.Property(f"{PMSprint} has {Integer:end_date}")
PMSprint.complete_date = model.Property(f"{PMSprint} has {Integer:complete_date}")
PMSprint.state = model.Property(f"{PMSprint} has {String:state}")

# ── Relationships (concept-to-concept links) ─────────────────────
# Cross-system linking (different identity systems)
GitHubUser.pm_user_mapping = model.Relationship(
    f"{GitHubUser} links to {PMUser}", short_name="github_pm_user_mapping")
GitHubPullRequest.implements_issue = model.Relationship(
    f"{GitHubPullRequest} implements {PMIssue}",
    short_name="github_pr_to_pm_issue")

# Within GitHub
GitHubUser.created_pr = model.Relationship(
    f"{GitHubUser} created {GitHubPullRequest}", short_name="github_user_created_pr")
GitHubRepository.contains_pr = model.Relationship(
    f"{GitHubRepository} contains {GitHubPullRequest}", short_name="repository_pull_requests")
GitHubPullRequest.contains_commit = model.Relationship(
    f"{GitHubPullRequest} contains {GitHubCommit}", short_name="pull_request_commits")
GitHubUser.belongs_to_team = model.Relationship(
    f"{GitHubUser} belongs to {GitHubTeam}", short_name="github_team_membership")

# Within project management
PMEpic.contains_issue = model.Relationship(
    f"{PMEpic} contains {PMIssue}", short_name="pm_epic_contains_issue")
PMIssue.assigned_to = model.Relationship(
    f"{PMIssue} assigned to {PMUser}", short_name="pm_issue_assignment")
PMIssue.in_sprint = model.Relationship(
    f"{PMIssue} assigned to {PMSprint}", short_name="pm_issue_sprint_assignment")
PMIssue.belongs_to_project = model.Relationship(
    f"{PMIssue} belongs to {PMProject}", short_name="pm_issue_project_membership")

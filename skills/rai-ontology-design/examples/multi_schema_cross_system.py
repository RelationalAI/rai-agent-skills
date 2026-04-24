"""Multi-schema cross-system — 4 domains, individual Properties, cross-system linking.

NOTE: Design-only example (requires Snowflake tables). Multi-schema (4 domains),
cross-system entity linking, and domain-prefixed concept names for collision avoidance.

Patterns: Multi-schema sources (4 organizational domains), many concepts with
simple identity, Property for all scalar attributes (not bundled Relationships),
Relationship for cross-system links (System A <-> System B),
prefixed concept names for collision avoidance.
Best practices: Property for scalars and functional FKs; Relationship for multi-valued links.
"""
from relationalai.semantics import Model, Date, DateTime, Float, Integer, String

model = Model("Cross-System Integration")

# ── Source Tables (multi-schema: 4 domains, 30+ tables) ──────────
class Sources:
    class ops_db:
        class system_a:
            jobs = model.Table("OPS_DB.SYSTEM_A.JOBS")
            runners = model.Table("OPS_DB.SYSTEM_A.RUNNERS")
            activity = model.Table("OPS_DB.SYSTEM_A.ACTIVITY")
            deployment = model.Table("OPS_DB.SYSTEM_A.DEPLOYMENT")
            ticket = model.Table("OPS_DB.SYSTEM_A.TICKET")
            work_item = model.Table("OPS_DB.SYSTEM_A.WORK_ITEM")
            work_item_review = model.Table("OPS_DB.SYSTEM_A.WORK_ITEM_REVIEW")
            project = model.Table("OPS_DB.SYSTEM_A.PROJECT")
            team = model.Table("OPS_DB.SYSTEM_A.TEAM")
            user = model.Table("OPS_DB.SYSTEM_A.USER")
            workflow = model.Table("OPS_DB.SYSTEM_A.WORKFLOW")
            workflow_run = model.Table("OPS_DB.SYSTEM_A.WORKFLOW_RUN")
        class system_b:
            board = model.Table("OPS_DB.SYSTEM_B.BOARD")
            comment = model.Table("OPS_DB.SYSTEM_B.COMMENT")
            component = model.Table("OPS_DB.SYSTEM_B.COMPONENT")
            epic = model.Table("OPS_DB.SYSTEM_B.EPIC")
            task = model.Table("OPS_DB.SYSTEM_B.TASK")
            project = model.Table("OPS_DB.SYSTEM_B.PROJECT")
            iteration = model.Table("OPS_DB.SYSTEM_B.ITERATION")
            user = model.Table("OPS_DB.SYSTEM_B.USER")
            version = model.Table("OPS_DB.SYSTEM_B.VERSION")
            worklog = model.Table("OPS_DB.SYSTEM_B.WORKLOG")
        class infra:
            consumer_account = model.Table("OPS_DB.INFRA.CONSUMER_ACCOUNT")
            engine = model.Table("OPS_DB.INFRA.ENGINE")
            transaction = model.Table("OPS_DB.INFRA.TRANSACTION")
        class platform_api:
            data_streams = model.Table("OPS_DB.PLATFORM_API.DATA_STREAMS")
            databases = model.Table("OPS_DB.PLATFORM_API.DATABASES")
            engines = model.Table("OPS_DB.PLATFORM_API.ENGINES")
            transactions = model.Table("OPS_DB.PLATFORM_API.TRANSACTIONS")

# ── Concepts ─────────────────────────────────────────────────────
# System A domain
SystemAUser = model.Concept("SystemAUser", identify_by={"id": Integer})
model.define(SystemAUser.new(id=Sources.ops_db.system_a.user.id))

SystemAProject = model.Concept("SystemAProject", identify_by={"id": Integer})
model.define(SystemAProject.new(id=Sources.ops_db.system_a.project.id))

SystemAWorkItem = model.Concept("SystemAWorkItem", identify_by={"id": Integer})
model.define(SystemAWorkItem.new(id=Sources.ops_db.system_a.work_item.id))

SystemAActivity = model.Concept("SystemAActivity", identify_by={"sha": String})
model.define(SystemAActivity.new(sha=Sources.ops_db.system_a.activity.sha))

SystemAWorkflow = model.Concept("SystemAWorkflow", identify_by={"id": Integer})
model.define(SystemAWorkflow.new(id=Sources.ops_db.system_a.workflow.id))

SystemAJob = model.Concept("SystemAJob", identify_by={"job_id": Integer})
model.define(SystemAJob.new(job_id=Sources.ops_db.system_a.jobs.job_id))

SystemATeam = model.Concept("SystemATeam", identify_by={"id": Integer})
model.define(SystemATeam.new(id=Sources.ops_db.system_a.team.id))

# System B domain
SystemBProject = model.Concept("SystemBProject", identify_by={"id": Integer})
model.define(SystemBProject.new(id=Sources.ops_db.system_b.project.id))

SystemBTask = model.Concept("SystemBTask", identify_by={"id": Integer})
model.define(SystemBTask.new(id=Sources.ops_db.system_b.task.id))

SystemBIteration = model.Concept("SystemBIteration", identify_by={"id": Integer})
model.define(SystemBIteration.new(id=Sources.ops_db.system_b.iteration.id))

SystemBEpic = model.Concept("SystemBEpic", identify_by={"id": Integer})
model.define(SystemBEpic.new(id=Sources.ops_db.system_b.epic.id))

SystemBUser = model.Concept("SystemBUser", identify_by={"id": String})
model.define(SystemBUser.new(id=Sources.ops_db.system_b.user.id))

# ── Properties (scalar attributes — individual, not bundled) ─────
# System A user
SystemAUser.login = model.Property(f"{SystemAUser} has {String:login}")
SystemAUser.name = model.Property(f"{SystemAUser} has {String:name}")
SystemAUser.company = model.Property(f"{SystemAUser} has {String:company}")
SystemAUser.bio = model.Property(f"{SystemAUser} has {String:bio}")
SystemAUser.location = model.Property(f"{SystemAUser} has {String:location}")
SystemAUser.is_site_admin = model.Relationship(f"{SystemAUser} is site admin")
SystemAUser.created_at = model.Property(f"{SystemAUser} has {Integer:created_at}")

# System A project
SystemAProject.name = model.Property(f"{SystemAProject} has {String:name}")
SystemAProject.full_name = model.Property(f"{SystemAProject} has {String:full_name}")
SystemAProject.is_private = model.Relationship(f"{SystemAProject} is private")
SystemAProject.description = model.Property(f"{SystemAProject} has {String:description}")
SystemAProject.primary_language = model.Property(f"{SystemAProject} has {String:primary_language}")
SystemAProject.fork_count = model.Property(f"{SystemAProject} has {Integer:fork_count}")
SystemAProject.watcher_count = model.Property(f"{SystemAProject} has {Integer:watcher_count}")
SystemAProject.is_archived = model.Relationship(f"{SystemAProject} is archived")
SystemAProject.default_branch = model.Property(f"{SystemAProject} has {String:default_branch}")

# System A work item
SystemAWorkItem.created_at = model.Property(f"{SystemAWorkItem} has {Integer:created_at}")
SystemAWorkItem.updated_at = model.Property(f"{SystemAWorkItem} has {Integer:updated_at}")
SystemAWorkItem.closed_at = model.Property(f"{SystemAWorkItem} has {Integer:closed_at}")
SystemAWorkItem.merge_commit_sha = model.Property(f"{SystemAWorkItem} has {String:merge_commit_sha}")
SystemAWorkItem.is_draft = model.Relationship(f"{SystemAWorkItem} is draft")
SystemAWorkItem.head_ref = model.Property(f"{SystemAWorkItem} has {String:head_ref}")
SystemAWorkItem.base_ref = model.Property(f"{SystemAWorkItem} has {String:base_ref}")

# System A activity
SystemAActivity.message = model.Property(f"{SystemAActivity} has {String:message}")
SystemAActivity.timestamp = model.Property(f"{SystemAActivity} has {Integer:timestamp}")
SystemAActivity.committer_name = model.Property(f"{SystemAActivity} has {String:committer_name}")
SystemAActivity.author_name = model.Property(f"{SystemAActivity} has {String:author_name}")

# System B task
SystemBTask.summary = model.Property(f"{SystemBTask} has {String:summary}")
SystemBTask.description = model.Property(f"{SystemBTask} has {String:description}")
SystemBTask.original_estimate = model.Property(f"{SystemBTask} has {Float:original_estimate}")
SystemBTask.remaining_estimate = model.Property(f"{SystemBTask} has {Float:remaining_estimate}")
SystemBTask.time_spent = model.Property(f"{SystemBTask} has {Float:time_spent}")

# System B iteration
SystemBIteration.start_date = model.Property(f"{SystemBIteration} has {Integer:start_date}")
SystemBIteration.end_date = model.Property(f"{SystemBIteration} has {Integer:end_date}")
SystemBIteration.complete_date = model.Property(f"{SystemBIteration} has {Integer:complete_date}")
SystemBIteration.state = model.Property(f"{SystemBIteration} has {String:state}")

# ── Multi-valued concept-to-concept associations (Relationship) ─────────────────────
# Cross-system linking (different identity systems)
SystemAUser.system_b_user_mapping = model.Relationship(
    f"{SystemAUser} links to {SystemBUser}", short_name="system_a_system_b_user_mapping")
SystemAWorkItem.implements_task = model.Relationship(
    f"{SystemAWorkItem} implements {SystemBTask}",
    short_name="system_a_work_item_to_system_b_task")

# Within System A
SystemAUser.created_work_item = model.Relationship(
    f"{SystemAUser} created {SystemAWorkItem}", short_name="system_a_user_created_work_item")
SystemAProject.contains_work_item = model.Relationship(
    f"{SystemAProject} contains {SystemAWorkItem}", short_name="system_a_project_work_items")
SystemAWorkItem.contains_activity = model.Relationship(
    f"{SystemAWorkItem} contains {SystemAActivity}", short_name="system_a_work_item_activities")
SystemAUser.belongs_to_team = model.Relationship(
    f"{SystemAUser} belongs to {SystemATeam}", short_name="system_a_team_membership")

# Within System B
SystemBEpic.contains_task = model.Relationship(
    f"{SystemBEpic} contains {SystemBTask}", short_name="system_b_epic_contains_task")
SystemBTask.assigned_to = model.Relationship(
    f"{SystemBTask} assigned to {SystemBUser}", short_name="system_b_task_assignment")
SystemBTask.in_iteration = model.Relationship(
    f"{SystemBTask} assigned to {SystemBIteration}", short_name="system_b_task_iteration_assignment")
SystemBTask.belongs_to_project = model.Relationship(
    f"{SystemBTask} belongs to {SystemBProject}", short_name="system_b_task_project_membership")

# ── Representative data bindings ─────────────────────────────────
# Illustrative subset showing the three binding patterns used across this model:
# (a) scalar property binding via filter_by + property call,
# (b) within-system FK relationship via filter_by on both ends,
# (c) cross-system FK relationship via a shared business key (e.g., email).
# The remaining concepts/properties follow the same patterns against their source tables.

# (a) Scalar properties — System A user
system_a_user = Sources.ops_db.system_a.user
model.define(
    SystemAUser.filter_by(id=system_a_user.id)
    .login(system_a_user.login)
)
model.define(
    SystemAUser.filter_by(id=system_a_user.id)
    .name(system_a_user.name)
)
model.define(SystemAUser.is_site_admin()).where(
    SystemAUser.filter_by(id=system_a_user.id),
    system_a_user.site_admin == True,
)

# (b) Within-system FK — work item belongs to project
work_item = Sources.ops_db.system_a.work_item
model.define(SystemAProject.contains_work_item(SystemAWorkItem)).where(
    SystemAProject.filter_by(id=work_item.project_id),
    SystemAWorkItem.filter_by(id=work_item.id),
)

# (c) Cross-system FK — System A user linked to System B user via shared email
# (email isn't an ID on either side, so join on the shared business key)
system_a_user_email = system_a_user.email
system_b_user = Sources.ops_db.system_b.user
model.define(SystemAUser.system_b_user_mapping(SystemBUser)).where(
    SystemAUser.filter_by(id=system_a_user.id),
    SystemBUser.filter_by(id=system_b_user.id),
    system_a_user_email == system_b_user.email,
)

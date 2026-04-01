# NOTE: Design-only example — demonstrates the LEGACY modeler export format.
# Detection signals: initialize() wrapper, _Concept prefix, Property/Relationship
# with "{...}" string syntax (not f-strings), standalone define() import
# (not model.define()), .where() binding (not filter_by()).
# For the LATEST modeler format (top-level model, Sources class, filter_by),
# see any other example in this directory.
# See also: references/modeler-and-composition.md for format detection and migration.

"""Modeler Legacy Export — Trimmed example of the legacy (alpha) modeler export format.

This is a representative subset extracted from a real modeler-generated model.
The legacy format is recognized by: initialize() function wrapper, _Concept prefix,
Property/Relationship with "{...}" string syntax, standalone define() calls,
.where() for data binding instead of filter_by().

For the latest modeler format, see modeler-and-composition.md § Latest format.
"""
from relationalai.semantics import Model, define
from relationalai.semantics.internal.snowflake import Table


def initialize(model: Model):
    Concept, Relationship, Property = model.Concept, model.Relationship, model.Property

    # --- Tables ---

    # --- SOURCE TABLE ---
    # source_fqn          : RAI_GITHUB_JIRA.JIRA.EPIC
    # column_count        : 6
    # columns             : ID:NUMBER, KEY:TEXT, NAME:TEXT, SUMMARY:TEXT, DONE:BOOLEAN
    TABLE__EPIC = Table("RAI_GITHUB_JIRA.JIRA.EPIC")

    # --- SOURCE TABLE ---
    # source_fqn          : RAI_GITHUB_JIRA.JIRA.PROJECT
    # column_count        : 11
    # columns             : ID:NUMBER, KEY:TEXT, NAME:TEXT, PROJECT_TYPE_KEY:TEXT, ...
    TABLE__PROJECT = Table("RAI_GITHUB_JIRA.JIRA.PROJECT")

    # --- SOURCE TABLE ---
    # source_fqn          : RAI_GITHUB_JIRA.JIRA.ISSUE
    # column_count        : 19
    # columns             : ID:NUMBER, KEY:TEXT, SUMMARY:TEXT, PROJECT_ID:NUMBER, ...
    TABLE__ISSUE = Table("RAI_GITHUB_JIRA.JIRA.ISSUE")

    # --- SOURCE TABLE ---
    # source_fqn          : RAI_GITHUB_JIRA.JIRA.USER
    # column_count        : 8
    # columns             : ID:TEXT, NAME:TEXT, EMAIL:TEXT, IS_ACTIVE:BOOLEAN, ...
    TABLE__USER = Table("RAI_GITHUB_JIRA.JIRA.USER")

    # --- Concepts ---
    # Legacy pattern: _Concept prefix, Property for identity, standalone define()

    # --- CONCEPT ---
    # concept_id          : c_jira_epic
    _JiraEpic = Concept("JiraEpic")
    _JiraEpic.id = Property("{JiraEpic} has id {id:Integer}")
    define(_JiraEpic.new(id=TABLE__EPIC.id))

    # --- CONCEPT ---
    # concept_id          : c_jira_project
    _JiraProject = Concept("JiraProject")
    _JiraProject.id = Property("{JiraProject} has id {id:Integer}")
    define(_JiraProject.new(id=TABLE__PROJECT.id))

    # --- CONCEPT ---
    # concept_id          : c_jira_issue
    _JiraIssue = Concept("JiraIssue")
    _JiraIssue.id = Property("{JiraIssue} has id {id:Integer}")
    define(_JiraIssue.new(id=TABLE__ISSUE.id))

    # --- CONCEPT ---
    # concept_id          : c_jira_user
    _JiraUser = Concept("JiraUser")
    _JiraUser.id = Property("{JiraUser} has id {id:String}")
    define(_JiraUser.new(id=TABLE__USER.id))

    # --- Relationship Definitions ---
    # Legacy pattern: ALL fields use Relationship (not Property), "{...}" strings,
    # define().where() for data binding instead of filter_by()

    # --- RELATIONSHIP DEFINITION (property-like) ---
    _JiraEpic.key = Relationship("{JiraEpic} has {key:String}")
    define(_JiraEpic.key(TABLE__EPIC.KEY)).where(
        _JiraEpic.id == TABLE__EPIC.id
    )

    _JiraEpic.name = Relationship("{JiraEpic} has {name:String}")
    define(_JiraEpic.name(TABLE__EPIC.NAME)).where(
        _JiraEpic.id == TABLE__EPIC.id
    )

    _JiraEpic.summary = Relationship("{JiraEpic} has {summary:String}")
    define(_JiraEpic.summary(TABLE__EPIC.SUMMARY)).where(
        _JiraEpic.id == TABLE__EPIC.id
    )

    # --- RELATIONSHIP DEFINITION (property-like) ---
    _JiraProject.key = Relationship("{JiraProject} has {key:String}")
    define(_JiraProject.key(TABLE__PROJECT.KEY)).where(
        _JiraProject.id == TABLE__PROJECT.id
    )

    _JiraProject.name = Relationship("{JiraProject} has {name:String}")
    define(_JiraProject.name(TABLE__PROJECT.NAME)).where(
        _JiraProject.id == TABLE__PROJECT.id
    )

    # --- RELATIONSHIP DEFINITION (FK link) ---
    _JiraIssue.key = Relationship("{JiraIssue} has {key:String}")
    define(_JiraIssue.key(TABLE__ISSUE.KEY)).where(
        _JiraIssue.id == TABLE__ISSUE.id
    )

    _JiraIssue.summary = Relationship("{JiraIssue} has {summary:String}")
    define(_JiraIssue.summary(TABLE__ISSUE.SUMMARY)).where(
        _JiraIssue.id == TABLE__ISSUE.id
    )

    # FK relationship: Issue -> Project (concept-to-concept link)
    _JiraIssue.project = Relationship("{JiraIssue} belongs to {JiraProject}")
    define(_JiraIssue.project(_JiraProject)).where(
        _JiraIssue.id == TABLE__ISSUE.id,
        _JiraProject.id == TABLE__ISSUE.PROJECT_ID,
    )

    # FK relationship: Issue -> User (assignee)
    _JiraIssue.assignee = Relationship("{JiraIssue} assigned to {JiraUser}")
    define(_JiraIssue.assignee(_JiraUser)).where(
        _JiraIssue.id == TABLE__ISSUE.id,
        _JiraUser.id == TABLE__ISSUE.ASSIGNEE_ID,
    )

    # --- RELATIONSHIP DEFINITION (property-like) ---
    _JiraUser.name = Relationship("{JiraUser} has {name:String}")
    define(_JiraUser.name(TABLE__USER.NAME)).where(
        _JiraUser.id == TABLE__USER.id
    )

    _JiraUser.email = Relationship("{JiraUser} has {email:String}")
    define(_JiraUser.email(TABLE__USER.EMAIL)).where(
        _JiraUser.id == TABLE__USER.id
    )

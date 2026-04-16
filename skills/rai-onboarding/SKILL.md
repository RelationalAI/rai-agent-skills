---
name: rai-onboarding
description: Guides first-time RelationalAI (RAI) setup end-to-end — install, connect to Snowflake, validate, and run a starter program. Use when starting a new RAI project or environment.
---

# RelationalAI
<!-- v1-STABLE -->
Build AI that is aligned to your business, grounded in your semantic model, and powered by the advanced reasoners of the RelationalAI decision intelligence platform. Learn more at [relational.ai](https://relational.ai)

This skill refers to the [relationalai Python package](https://pypi.org/project/relationalai) aka PyRel. Ensure the package is installed in your environment.

This allows you to write PyRel programs and use the `rai` CLI tool.

## Summary

**What:** Guides first-time setup of the RelationalAI platform — installing the Python package, connecting to Snowflake, validating the environment, and running a starter program.

**When to use:**
- User is setting up RelationalAI for the first time
- User needs help installing the `relationalai` Python package or configuring the Snowflake connection
- User asks "how do I get started with RAI?" or "how do I connect to my Snowflake account?"
- User wants to run their first PyRel program

**When NOT to use:**
- Writing PyRel models or queries — see `rai-pyrel-coding`
- Designing ontology structure — see `rai-ontology-design`
- Configuring engines, profiles, or advanced settings — see `rai-configuration`
- Discovering what questions an existing model can answer — see `rai-discovery`

---

## Quick Reference

| Step | Action | Key Command |
|------|--------|-------------|
| 1 | Install package | `pip install relationalai` or `uv add relationalai` |
| 2 | Establish connection | Use existing Snowflake/DBT config or `rai init` |
| 3 | Validate connection | `rai connect` (check MFA) |
| 4 | Create sample program | Use inline data or user's domain |
| 5 | Propose next steps | Adapt to real data, enhance sample, or use [project templates](https://docs.relational.ai/build/templates) |

---

## Prerequisites

The RelationalAI Native App for Snowflake must be installed in your account by an administrator.
- Request access [here](https://app.snowflake.com/marketplace/listing/GZTYZOOIX8H/relationalai-relationalai). 
- See the [RAI Native App docs](https://docs.relational.ai/manage/install) for details.

The `rai_developer` role is the standard role for running PyRel programs. Custom Snowflake roles can also work if granted the `rai_user` application role — see [User Access](https://docs.relational.ai/manage/user-access) for details.

## Contact
- support@relational.ai
- sales@relational.ai
- [official documentation](https://docs.relational.ai/)

## Mandatory instructions
- Help the user configure the environment (both Python and RelationalAI/Snowflake).
- Leverage the user's preferred tools and configs for managing Python
- If there are issues, share links to the docs and contact emails 
- Leverage the Python API documentation that ships with the source

## Onboarding Workflow (first-time setup only)
Users are expected to be Snowflake users with existing credentials.
Walk the user through the following steps one-by-one and in order. 
For each step, explain what it will accomplish and prompt the user for the necessary input for you to perform that step on their behalf.

### Step 1. Install the package
```
pip install relationalai
# or
uv add relationalai
```

### Step 2. Establish the connection
There are 2 options:
1) Rely on an existing Snowflake (`~/.snowflake/config.toml`) or DBT (`~/.dbt/profiles.yml`) connection. Simply run `rai` or a PyRel program and the connection will be automatically picked up.
2) Use `rai init` to create a `raiconfig.yaml` which needs to be filled in. Use the `rai-configuration` skill to help the user fill out the fields.

### Step 3. Validate the connection
Run this command to validate the basic configuration works:
`rai connect`. Remind the user to check their MFA. Revisit Step 2 if there are issues.

### Step 4. Create a sample
Offer to create a small sample program using inline data.
Check if the user has a domain or analytical use case they want to see the sample in. Otherwise set up a generic use case for customer segmentation using graph analysis (see `rai-graph-analysis` examples).
Reference the `pyrel-coding` skill for syntax and `rai-graph-analysis` for graph patterns.
Ensure the sample runs and the user can see the output.
Offer to explain the different components of the program.

### Step 5. Propose next steps
Now that the basics are in place, it's time to show off RelationalAI's potential.
Propose either
1) adapting the sample to actual data in Snowflake tables
2) enhance the sample with more sophisticated segmentation semantics, or to support different types of analysis.
3) share the [project templates](https://docs.relational.ai/build/templates) link and invite the user to choose one.

## Common Pitfalls

| Mistake                                           | Cause                                                                    | Fix                                                                 |
|---------------------------------------------------|--------------------------------------------------------------------------|---------------------------------------------------------------------|
| Errors about RelationalAI Native App not existing | Either the NA hasn't been installed, or the user's current role lacks access | Verify the Native App is installed and the current role has `rai_developer` or a custom role granted the `rai_user` application role |

---

## Important Skills
- `rai-pyrel-coding`: Write PyRel (use always)
- `rai-ontology-design`: Design PyRel models (use for modeling complicated domains & use cases)
- `rai-discovery`: Discover questions to answer or problems to solve — surfaces what the data can support and routes to the right reasoner workflow

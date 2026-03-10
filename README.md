# RelationalAI Agent Skills

Empower your coding agent with the decision intelligence capabilities of [RelationalAI](https://relational.ai).

## Installation

TODO while the repo is private, use `git@github.com:RelationalAI/rai-agent-skills.git` instead of `RelationalAI/rai-agent-skills`

### Generic

If you can, use [Vercel's skills CLI](https://github.com/vercel-labs/skills) (requres `npm` v5.2.0+). It helps you manage & update skills for most coding agents.
```bash
 $ npx skills add RelationalAI/rai-agent-skills
 # optionally specify agents to target
 $ npx skills add RelationalAI/rai-agent-skills \
  --agent claude-code \
  --agent cortex \
  --agent codex
```

You can also directly copy the `skills/` folder into your coding agent configuration.

We recommend either `npx skills` or an agent-specific method so that it's easy to keep up to date.

### Claude
Follow [these instructions](https://code.claude.com/docs/en/discover-plugins#add-marketplaces) to point at this repo.

Example:
```
/plugin marketplace add RelationalAI/rai-agent-skills
/plugin install rai@RelationalAI
# or use the wizard
/plugin 
```
Restart your session after installing.

### Cortex Code
Follow [these instructions](https://docs.snowflake.com/en/user-guide/cortex-code/extensibility#skills).

In short, clone this repo to your file system then use the `/skill` dialog to add the folder.

### VSCode
Follow [these instructions](https://code.visualstudio.com/docs/copilot/customization/agent-plugins#_configure-plugin-marketplaces) to point at this repo.

Example:
```
// settings.json
"chat.plugins.marketplaces": [
    "RelationalAI/rai-agent-skills"
]
```


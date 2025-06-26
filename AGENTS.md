# Task Master AI - Claude Code Integration Guide

## Essential Commands

### Core Workflow Commands

```bash
# Project Setup
# Initialize Task Master in current project
task-master init
# Generate tasks from PRD document
task-master parse-prd .taskmaster/docs/prd.txt
# Configure AI models interactively
task-master models --setup

# Daily Development Workflow
# Show all tasks with status
task-master list
# Get next available task to work on
task-master next
# View detailed task information (e.g., task-master show 1.2)
task-master show <id>
# Mark task complete
task-master set-status --id=<id> --status=done

# Task Management
# Add new task with AI assistance
task-master add-task --prompt="description" --research
# Break task into subtasks
task-master expand --id=<id> --research --force
# Update specific task
task-master update-task --id=<id> --prompt="changes"
# Update multiple tasks from ID onwards
task-master update --from=<id> --prompt="changes"
# Add implementation notes to subtask
task-master update-subtask --id=<id> --prompt="notes"

# Analysis & Planning
# Analyze task complexity
task-master analyze-complexity --research
# View complexity analysis
task-master complexity-report
# Expand all eligible tasks
task-master expand --all --research

# Dependencies & Organization
# Add task dependency
task-master add-dependency --id=<id> --depends-on=<id>
# Reorganize task hierarchy
task-master move --from=<id> --to=<id>
# Check for dependency issues
task-master validate-dependencies
# Update task markdown files (usually auto-called)
task-master generate
```

## Key Files & Project Structure

### Core Files

- `.taskmaster/tasks/tasks.json` - Main task data file (auto-managed)
- `.taskmaster/config.json` - AI model configuration (use
  `task-master models` to modify)
- `.taskmaster/docs/prd.txt` - Product Requirements Document for parsing
- `.taskmaster/tasks/*.txt` - Individual task files (auto-generated
  from tasks.json)
- `.env` - API keys for CLI usage

### Claude Code Integration Files

- `CLAUDE.md` - Auto-loaded context for Claude Code (this file)
- `.claude/settings.json` - Claude Code tool allowlist and preferences
- `.claude/commands/` - Custom slash commands for repeated workflows
- `.mcp.json` - MCP server configuration (project-specific)

### Directory Structure

```text
project/
├── .taskmaster/
│   ├── tasks/              # Task files directory
│   │   ├── tasks.json      # Main task database
│   │   ├── task-1.md      # Individual task files
│   │   └── task-2.md
│   ├── docs/              # Documentation directory
│   │   ├── prd.txt        # Product requirements
│   ├── reports/           # Analysis reports directory
│   │   └── task-complexity-report.json
│   ├── templates/         # Template files
│   │   └── example_prd.txt  # Example PRD template
│   └── config.json        # AI models & settings
├── .claude/
│   ├── settings.json      # Claude Code configuration
│   └── commands/         # Custom slash commands
├── .env                  # API keys
├── .mcp.json            # MCP configuration
└── CLAUDE.md            # This file - auto-loaded by Claude Code
```

## MCP Integration

Task Master provides an MCP server that Claude Code can connect to.
Configure in `.mcp.json`:

```json
{
  "mcpServers": {
    "task-master-ai": {
      "command": "npx",
      "args": ["-y", "--package=task-master-ai", "task-master-ai"],
      "env": {
        "ANTHROPIC_API_KEY": "your_key_here",
        "PERPLEXITY_API_KEY": "your_key_here",
        "OPENAI_API_KEY": "OPENAI_API_KEY_HERE",
        "GOOGLE_API_KEY": "GOOGLE_API_KEY_HERE",
        "XAI_API_KEY": "XAI_API_KEY_HERE",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY_HERE",
        "MISTRAL_API_KEY": "MISTRAL_API_KEY_HERE",
        "AZURE_OPENAI_API_KEY": "AZURE_OPENAI_API_KEY_HERE",
        "OLLAMA_API_KEY": "OLLAMA_API_KEY_HERE"
      }
    }
  }
}
```

### Essential MCP Tools

```javascript
help; // = shows available taskmaster commands
// Project setup
initialize_project; // = task-master init
parse_prd; // = task-master parse-prd

// Daily workflow
get_tasks; // = task-master list
next_task; // = task-master next
get_task; // = task-master show <id>
set_task_status; // = task-master set-status

// Task management
add_task; // = task-master add-task
expand_task; // = task-master expand
update_task; // = task-master update-task
update_subtask; // = task-master update-subtask
update; // = task-master update

// Analysis
analyze_project_complexity; // = task-master analyze-complexity
complexity_report; // = task-master complexity-report
```

## Claude Code Workflow Integration

### Standard Development Workflow

#### 1. Project Initialization

```bash
# Initialize Task Master
task-master init

# Create or obtain PRD, then parse it
task-master parse-prd .taskmaster/docs/prd.txt

# Analyze complexity and expand tasks
task-master analyze-complexity --research
task-master expand --all --research
```

If tasks already exist, another PRD can be parsed (with new information
only!) using parse-prd with --append flag. This will add the generated
tasks to the existing list of tasks.

#### 2. Daily Development Loop

```bash
# Start each session
# Find next available task
task-master next
# Review task details
task-master show <id>

# During implementation, check in code context into the tasks and subtasks
task-master update-subtask --id=<id> --prompt="implementation notes..."

# Complete tasks
task-master set-status --id=<id> --status=done
```

#### 3. Multi-Claude Workflows

For complex projects, use multiple Claude Code sessions:

```bash
# Terminal 1: Main implementation
cd project && claude

# Terminal 2: Testing and validation
cd project-test-worktree && claude

# Terminal 3: Documentation updates
cd project-docs-worktree && claude
```

### Custom Slash Commands

Create `.claude/commands/taskmaster-next.md`:

```markdown
Find the next available Task Master task and show its details.

Steps:

1. Run `task-master next` to get the next task
2. If a task is available, run `task-master show <id>` for full details
3. Provide a summary of what needs to be implemented
4. Suggest the first implementation step
```

Create `.claude/commands/taskmaster-complete.md`:

```markdown
Complete a Task Master task: $ARGUMENTS

Steps:

1. Review the current task with `task-master show $ARGUMENTS`
2. Verify all implementation is complete
3. Run any tests related to this task
4. Mark as complete: `task-master set-status --id=$ARGUMENTS --status=done`
5. Show the next available task with `task-master next`
```

## Tool Allowlist Recommendations

Add to `.claude/settings.json`:

```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "Bash(git commit:*)",
    "Bash(git add:*)",
    "Bash(npm run *)",
    "mcp__task_master_ai__*"
  ]
}
```

## Configuration & Setup

### API Keys Required

At least **one** of these API keys must be configured:

- `ANTHROPIC_API_KEY` (Claude models) - **Recommended**
- `PERPLEXITY_API_KEY` (Research features) - **Highly recommended**
- `OPENAI_API_KEY` (GPT models)
- `GOOGLE_API_KEY` (Gemini models)
- `MISTRAL_API_KEY` (Mistral models)
- `OPENROUTER_API_KEY` (Multiple models)
- `XAI_API_KEY` (Grok models)

An API key is required for any provider used across any of the 3 roles
defined in the `models` command.

### Model Configuration

```bash
# Interactive setup (recommended)
task-master models --setup

# Set specific models
task-master models --set-main claude-3-5-sonnet-20241022
task-master models --set-research perplexity-llama-3.1-sonar-large-128k-online
```

## Task Structure & IDs

### Task ID Format

- Main tasks: `1`, `2`, `3`, etc.
- Subtasks: `1.1`, `1.2`, `2.1`, etc.
- Sub-subtasks: `1.1.1`, `1.1.2`, etc.

### Task Status Values

- `pending` - Ready to work on
- `in-progress` - Currently being worked on
- `done` - Completed and verified
- `deferred` - Postponed
- `cancelled` - No longer needed
- `blocked` - Waiting on external factors

### Task Fields

```json
{
  "id": "1.2",
  "title": "Implement user authentication",
  "description": "Set up JWT-based auth system",
  "status": "pending",
  "priority": "high",
  "dependencies": ["1.1"],
  "details": "Use bcrypt for hashing, JWT for tokens...",
  "testStrategy": "Unit tests for auth functions, integration for login flow",
  "subtasks": []
}
```

## Claude Code Best Practices with Task Master

### Context Management

- Use `/clear` between different tasks to maintain focus
- This CLAUDE.md file is automatically loaded for context
- Use `task-master show <id>` to pull specific task context when needed

### Iterative Implementation

1. `task-master show <subtask-id>` - Understand requirements
2. Explore codebase and plan implementation
3. `task-master update-subtask --id=<id> --prompt="detailed plan"` - Log plan
4. `task-master set-status --id=<id> --status=in-progress` - Start work
5. Implement code following logged plan
6. `task-master update-subtask --id=<id> --prompt="what worked/didn't work"` -
   Log progress
7. `task-master set-status --id=<id> --status=done` - Complete task

### Complex Workflows with Checklists

For large migrations or multi-step processes:

1. Create a markdown PRD file describing the new changes:
   `touch task-migration-checklist.md` (prds can be .txt or .md)
2. Use Taskmaster to parse the new prd with
   `task-master parse-prd --append` (also available in MCP)
3. Use Taskmaster to expand the newly generated tasks into subtasks.
   Consider using `analyze-complexity` with the correct --to and --from IDs
   (the new ids) to identify the ideal subtask amounts for each task.
   Then expand them.
4. Work through items systematically, checking them off as completed
5. Use `task-master update-subtask` to log progress on each task/subtask
   and/or updating/researching them before/during implementation if
   getting stuck

### Git Integration

Task Master works well with `gh` CLI:

```bash
# Create PR for completed task
gh pr create --title "Complete task 1.2: User authentication" \
  --body "Implements JWT auth system as specified in task 1.2"

# Reference task in commits
git commit -m "feat: implement JWT auth (task 1.2)"
```

### Parallel Development with Git Worktrees

```bash
# Create worktrees for parallel task development
git worktree add ../project-auth feature/auth-system
git worktree add ../project-api feature/api-refactor

# Run Claude Code in each worktree
cd ../project-auth && claude    # Terminal 1: Auth work
cd ../project-api && claude     # Terminal 2: API work
```

## Troubleshooting

### AI Commands Failing

```bash
# Check API keys are configured
cat .env                           # For CLI usage

# Verify model configuration
task-master models

# Test with different model
task-master models --set-fallback gpt-4o-mini
```

### MCP Connection Issues

- Check `.mcp.json` configuration
- Verify Node.js installation
- Use `--mcp-debug` flag when starting Claude Code
- Use CLI as fallback if MCP unavailable

### Task File Sync Issues

```bash
# Regenerate task files from tasks.json
task-master generate

# Fix dependency issues
task-master fix-dependencies
```

DO NOT RE-INITIALIZE. That will not do anything beyond re-adding the same
Taskmaster core files.

## Important Notes

### AI-Powered Operations

These commands make AI calls and may take up to a minute:

- `parse_prd` / `task-master parse-prd`
- `analyze_project_complexity` / `task-master analyze-complexity`
- `expand_task` / `task-master expand`
- `expand_all` / `task-master expand --all`
- `add_task` / `task-master add-task`
- `update` / `task-master update`
- `update_task` / `task-master update-task`
- `update_subtask` / `task-master update-subtask`

### File Management

- Never manually edit `tasks.json` - use commands instead
- Never manually edit `.taskmaster/config.json` - use `task-master models`
- Task markdown files in `tasks/` are auto-generated
- Run `task-master generate` after manual changes to tasks.json

### Claude Code Session Management

- Use `/clear` frequently to maintain focused context
- Create custom slash commands for repeated Task Master workflows
- Configure tool allowlist to streamline permissions
- Use headless mode for automation: `claude -p "task-master next"`

### Multi-Task Updates

- Use `update --from=<id>` to update multiple future tasks
- Use `update-task --id=<id>` for single task updates
- Use `update-subtask --id=<id>` for implementation logging

### Research Mode

- Add `--research` flag for research-based AI enhancement
- Requires a research model API key like Perplexity (`PERPLEXITY_API_KEY`)
  in environment
- Provides more informed task creation and updates
- Recommended for complex technical tasks

## Git Strategy

### Branch-per-Task (BPT) strategy

- For every Taskmaster task create a dedicated branch:
  `task-<id>-<slug>` (e.g. `task-17-api-metrics-fix`).
- Base the branch on `master` (or the active feature tag's branch if
  using tags).

### Explicit confirmation before committing

- Stage (`git add -A`) **only after tests pass locally**.
- Ask the user for "OK to commit & push?" before every commit.
  - If *yes*: `git commit -m "<Conventional Commit>"` then
    `git push -u origin <branch>`.
  - If *no*: keep refining until approval.

### Atomic, Conventional Commits

- One logical change per commit; do not mix refactors with new features.
- Use Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, …).
- Include Task ID in the footer:

  ```text
  feat(api): add /metrics endpoint

  Task: #12
  ```

### Pull-Request & Merge rules

- Open a PR as soon as the first commit is pushed (draft OK).
- CI must be green (lint, type-check, tests, coverage ≥90 %) before PR
  can be marked ready.
- At least one approving review required.
- **Squash-merge** into `master` to keep history linear; PR title becomes
  squash commit.

### CI/CD pipeline tie-ins

- `push` or `pull_request` on any branch triggers the **CI matrix**
  (`.github/workflows/ci.yml`):
  1. Ruff / Black / Mypy linters
  2. Pytest + coverage gate (≥90 %)
  3. Optional perf job (`make perf`) on nightly cron
- `push` on `master` (post-merge) additionally:
  - Builds & pushes the Docker image to GHCR
  - Uploads nightly `pg_dump` backup artifacts
- Semantic version tag (`v*.*.*`) triggers Vercel/Supabase deploy workflow
  when those features land (Task 18).

### Rebasing & Syncing

- Keep branch up-to-date via `git pull --rebase origin master`.
- Resolve conflicts locally; re-run full test suite before pushing.

### Large / risky features

- If a feature spans several Taskmaster tasks:
  - Create an umbrella branch `feature/<name>` forked from `master`.
  - Open PR targeting `master`, then stack task branches on top and merge
    sequentially.

### Emergency fixes

- Branch from `master` → `hotfix/<issue>`
  - Fast-track through CI; reviewers may approve retrospectively if
    blocking production.

### Tag discipline

- Only CI/CD or release scripts create annotated tags
  (`git tag -a vX.Y.Z -m ...`).

### Pre-commit hooks (guard rails)

- `poetry run pre-commit install` on first clone.
- Hooks block pushes that violate formatting or lint rules.

### Documentation & traceability

- Link PRs to Taskmaster tasks (`Fixes TM-#<id>`) so the bot can
  automatically close them.
- Keep CHANGELOG updated via Changesets if public releases are cut.

---

*This guide ensures Claude Code has immediate access to Task Master's
essential functionality for agentic development workflows.*

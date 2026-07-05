# AI Dev Memory

This repository stores local-first memory for AI-assisted coding work.

The main workspace is `worklog/`. It captures AI work records, daily reports, weekly reports, and long-lived project memory. Each important project gets a folder that can be reviewed later for project information, work diary, business logic, key code, code style, personal development habits, decisions, and local environment details.

## Structure

```text
worklog/
  daily/             Daily AI work records and reports
  weekly/            Weekly rollups
  projects/
    <project-slug>/
      overview.md        Project information and current state
      work-diary.md      Project-specific work history
      business-logic.md  Product rules and domain behavior
      key-code.md        Important files, functions, modules, and commands
      code-style.md      Local code conventions and architecture style
      habits.md          Personal habits observed while working here
      decisions.md       Durable technical and workflow decisions
      environment.md     Local setup, services, tools, and machine details
  index.md           Main navigation
templates/           Reusable markdown templates
```

## Operating Rules

- Record facts from actual work.
- Keep notes short enough to review later.
- Promote reusable project knowledge into the matching `worklog/projects/<project-slug>/` file.
- Keep daily and weekly reports as timelines; keep project folders as long-term memory.
- Commit changes when a useful batch of notes is ready for GitHub.

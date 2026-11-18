# Future Work

This document records the local Streamlit workflow and the work planned for a later web app. One person uses the current version on the owner's computer. Other people will access it only after the migration.

## Current Local Workflow

- The local user should have saved projects in a collapsible sidebar. The main workspace should show a project title and emoji; assign a random emoji when none is chosen.
- A new project starts as a draft. Its owner can upload a CSV/XLSX file and select the sheet and title column before starting the first run.
- Reopening a project should restore the original upload, selections, search results, API notes, and downloaded PDFs/ZIP. After completion, the upload and results are locked and the project cannot run again; its name and emoji remain editable.
- An interrupted or failed run may be retried with the same upload when no run has completed. If the browser closes, mark the run interrupted rather than continuing it; show this state when the project reopens.
- The local user enters their own API keys through a Settings page reached from the bottom of the sidebar. Keep keys only for the current session and require re-entry after a restart. A close visual match to ChatGPT or Claude is not a priority.

## Local Storage and Retention

- Use SQLite for project records and a local data directory for uploads and PDFs. Keep both out of Git.
- Keep completed projects until the user explicitly deletes them. Confirm deletion, then remove the project record, uploaded workbook, results, and downloaded PDFs/ZIP.

## Later Multi-user Migration

- Add account sign-in before inviting multiple people to use the app. Give each person private projects and enforce ownership on every project, file, and download access path.
- Move from Streamlit to a dedicated web app with durable hosted storage. Migrate saved projects and keep the paper search and PDF verification behavior.
- Let searches continue after the browser closes, with progress and results available when the user returns.
- Decide between bring-your-own API keys and API access provided by the application; choose how credentials are stored and billed before implementing either model.

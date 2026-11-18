# Repository Guidelines

## Project Structure & Module Organization

`app.py` is the Streamlit interface for projects, settings, searches, and downloads. `project_store.py` persists project metadata in SQLite and files in `local_data/`. `paper_finder.py` handles CSV/XLSX loading, matching, scholarly API searches, PDF verification, and report/ZIP creation. Offline tests are in `test_project_store.py` and `test_paper_finder.py`. `requirements.txt` lists runtime dependencies; `README.md` explains the user workflow.

## Build, Test, and Development Commands

- `pip install -r requirements.txt` installs Streamlit and Requests. Use Python 3.10 or newer.
- `streamlit run app.py` starts the local web app. Searching and PDF retrieval require internet access.
- `python3 -m unittest` runs the offline `unittest` suite.
- `python test_paper_finder.py SAMPLE_FILE.xlsx` also checks a local workbook with a `Studies Export` sheet containing 14 titled rows. The sample file is optional and is not in the repository.

There is no separate build command.

## Coding Style & Naming Conventions

Use four-space indentation and follow the existing Python style. Name modules and functions with `snake_case`, classes with `PascalCase`, and tests with `test_` prefixes. Keep UI code in `app.py` and reusable retrieval logic in `paper_finder.py`. Use the standard library where practical; no formatter or linter is configured.

## Testing Guidelines

Add focused `unittest` cases to the matching test module for changes to storage, parsing, matching, downloads, or ZIP output. Mock scholarly API calls and downloads so the default suite stays offline. Run the suite before opening a pull request. There is no stated coverage threshold.

## Commit & Pull Request Guidelines

The available Git history has one commit, `Create FULLPDFLINK MVP`; it does not establish a detailed convention. Use a short, imperative commit subject that describes the change. In pull requests, explain the behavior changed and how it was tested; link a relevant issue when one exists. Include a screenshot for visible Streamlit changes.

## Security & Configuration

Keep API keys out of commits and test fixtures. Settings holds OpenAlex and Semantic Scholar keys only for the current browser session. Keep `local_data/` out of Git; it contains uploaded spreadsheets and downloaded PDFs. Preserve the original upload and verify downloaded content before treating it as a PDF.

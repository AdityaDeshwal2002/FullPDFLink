# Research PDF Finder

Create local projects, upload a `.xlsx` or `.csv`, choose the title column, and search for matching papers. Results include clickable **article links** and **PDF links**. Verified public PDFs are saved and offered as a ZIP. Your original spreadsheet is **not edited**, and no Free/Paid/From Client values are modified.

## How to run

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. The Streamlit page opens in your browser.
5. Click **New project**, edit its name or emoji, upload a spreadsheet, choose its sheet and title column, and save the selection.
6. Click **Find article links and PDFs**. Reopen the project from the sidebar to view its results, original file, and available PDFs. A completed project's upload and results are locked; its name and emoji remain editable.
7. Use **Settings** at the bottom of the sidebar to enter optional API keys. They last only for the current browser session.

Projects are stored in `local_data/` next to the app and are kept until you confirm deletion. Back up that folder if you want to preserve projects when moving the app. This version is for one person running it locally; account sign-in and private multi-user access are planned for the later web app. An interrupted run can be retried with the same spreadsheet.

Run `python3 -m unittest` for the offline tests.

## APIs

- **OpenAlex** — Primary title search, open-access PDF locations, and (with a free API key) cached PDF retrieval: https://help.openalex.org/api/
- **Europe PMC** — Biomedical papers and public full-text links: https://www.ebi.ac.uk/europepmc/webservices/rest/
- **Semantic Scholar** — Alternative title search and public PDF URLs: https://api.semanticscholar.org/api-docs/
- **Crossref** — Fallback title-based article matching: https://www.crossref.org/documentation/retrieve-metadata/rest-api/

An **OpenAlex API key** is recommended for larger batches and is required for downloads hosted on `content.openalex.org`. Add it on the Settings page. A Semantic Scholar API key is optional; heavy use without one may be rate-limited. Crossref does not require a key.

## Search scope

- Uses **title only** for searching and verifying the paper title. Other metadata columns aren't required.
- Automatically downloads **only strongly matching** papers whose accessible URLs return real PDF files.
- For other possible matches, supplies clickable URLs for you to inspect manually.
- Some publisher websites block scripted downloads, so a working PDF link can appear without a saved file.
- API requests and PDFs require an internet connection; publisher paywalls are not bypassed.
- CSV is a separate retrieval report, **not** a replacement for the original review workbook.

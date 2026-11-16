# Research PDF Finder — Streamlit MVP

Upload a `.xlsx` or `.csv`, choose the title column, and search for matching papers. Results include clickable **article links** and **PDF links**. Verified public PDFs are saved automatically and offered as a ZIP. Your original spreadsheet is **not edited**, and no Free/Paid/From Client values are modified.

## How to run

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Run:

   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```
4. The Streamlit page opens in your browser.
5. Upload your sample or another `.xlsx` file, choose `Studies Export` and the `Title` column, then click **Find article links and PDFs**.
6. Click article/PDF URLs in the results table, download the results CSV, and download the ZIP of successfully retrieved PDFs.

## APIs

- **OpenAlex** — Primary title search, open-access PDF locations, and (with a free API key) cached PDF retrieval: https://help.openalex.org/api/
- **Europe PMC** — Biomedical papers and public full-text links: https://www.ebi.ac.uk/europepmc/webservices/rest/
- **Semantic Scholar** — Alternative title search and public PDF URLs: https://api.semanticscholar.org/api-docs/
- **Crossref** — Fallback title-based article matching: https://www.crossref.org/documentation/retrieve-metadata/rest-api/

An **OpenAlex API key** is recommended for larger batches and is required for downloads hosted on `content.openalex.org`. You may add it in the sidebar. A Semantic Scholar API key is optional; heavy use without one may be rate-limited. Crossref does not require a key.

## Scope of this first version

- Uses **title only** for searching and verifying the paper title. Other metadata columns aren't required.
- Automatically downloads **only strongly matching** papers whose accessible URLs return real PDF files.
- For other possible matches, supplies clickable URLs for you to inspect manually.
- Some publisher websites block scripted downloads, so a working PDF link can appear without a saved file.
- API requests and PDFs require an internet connection; publisher paywalls are not bypassed.
- CSV is a separate retrieval report, **not** a replacement for the original review workbook.

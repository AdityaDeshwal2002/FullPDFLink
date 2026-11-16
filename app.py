"""Launch with: streamlit run app.py"""
from __future__ import annotations

import tempfile
from pathlib import Path

import requests
import streamlit as st

from paper_finder import find_one, load_sheets, make_zip, results_csv

st.set_page_config(page_title='Research PDF Finder', page_icon='📄', layout='wide')
st.title('📄 Research PDF Finder')
st.caption('Upload Excel → search paper titles → open links → download available PDFs.')

with st.sidebar:
    st.header('Optional API settings')
    openalex_key = st.text_input('OpenAlex API key', type='password', help='Recommended for larger batches and OpenAlex-hosted PDFs.')
    semantic_key = st.text_input('Semantic Scholar API key', type='password', help='Optional. Improves API access if you have a key.')
    email = st.text_input('Contact email (for Crossref)', placeholder='you@example.com')
    st.caption('Keys are only used during this run and are not written to the report.')

upload = st.file_uploader('Upload an Excel or CSV file', type=['xlsx', 'csv'])
if upload is None:
    st.info('Choose your spreadsheet to begin. Your original file will not be modified.')
    st.stop()

try:
    sheets = load_sheets(upload.getvalue(), upload.name)
except Exception as exc:
    st.error(f'Cannot read the file: {exc}')
    st.stop()

if not sheets:
    st.warning('No worksheets were found.')
    st.stop()

names = list(sheets)
selected_sheet = st.selectbox('Worksheet', names, index=names.index('Studies Export') if 'Studies Export' in names else 0)
records = sheets[selected_sheet]
if not records:
    st.warning('This worksheet has no data rows.')
    st.stop()

columns = list(records[0].keys())
title_matches = [col for col in columns if col.casefold().strip() == 'title']
title_col = st.selectbox('Title column', columns, index=columns.index(title_matches[0]) if title_matches else 0)
id_matches = [col for col in columns if col.casefold().strip() == 'id']
id_col = id_matches[0] if id_matches else None

items = [(str(row.get(id_col) or index) if id_col else str(index), str(row.get(title_col) or '').strip())
         for index, row in enumerate(records, start=1)]
items = [(identifier, title) for identifier, title in items if title]
st.write(f'**{len(items)} titles ready to search.**')
with st.expander('Preview the titles'):
    st.dataframe([{'ID': x, 'Title': y} for x, y in items], use_container_width=True, hide_index=True)

if st.button('🔎 Find article links and PDFs', type='primary', disabled=not items):
    root = Path(tempfile.mkdtemp(prefix='research_pdf_finder_'))
    folder = root / 'pdfs'
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': 'ResearchPDF-Finder/1.0 (academic article discovery)'})
    results = []
    progress = st.progress(0, text='Searching for articles…')
    for i, (identifier, title) in enumerate(items, 1):
        progress.progress((i - 1) / len(items), text=f'Study {i}/{len(items)}: {title[:76]}')
        results.append(find_one(title, identifier, folder, session,
                                openalex_key=openalex_key.strip(),
                                semantic_key=semantic_key.strip(), email=email.strip()))
    progress.progress(1.0, text='Search finished')
    zip_path = root / 'downloaded_pdfs.zip'
    make_zip(results, zip_path)
    st.session_state['paper_finder_results'] = results
    st.session_state['paper_finder_zip'] = str(zip_path)
    st.session_state['paper_finder_file_signature'] = (upload.name, len(upload.getvalue()), selected_sheet, title_col)

signature = (upload.name, len(upload.getvalue()), selected_sheet, title_col)
if st.session_state.get('paper_finder_file_signature') != signature:
    st.stop()

results = st.session_state.get('paper_finder_results', [])
if results:
    count_pdf = sum(x['Result'] == 'PDF downloaded' for x in results)
    count_links = sum(bool(x['Article link'] or x['PDF link']) for x in results)
    x, y, z = st.columns(3)
    x.metric('Titles searched', len(results))
    y.metric('Articles / links found', count_links)
    z.metric('PDFs downloaded', count_pdf)

    st.subheader('Results')
    st.dataframe([{k: row.get(k, '') for k in
                   ('ID', 'Input title', 'Matched title', 'Match', 'Source',
                    'Article link', 'PDF link', 'Result')} for row in results],
                 column_config={
                     'Article link': st.column_config.LinkColumn('Article link', display_text='Open article'),
                     'PDF link': st.column_config.LinkColumn('PDF link', display_text='Open PDF'),
                 }, use_container_width=True, hide_index=True, height=420)
    st.caption('Links may require a browser or institutional access. Only files verified as PDFs are saved. Close title matches should be checked manually.')

    col1, col2 = st.columns(2)
    with col1:
        st.download_button('⬇️ Download results CSV', data=results_csv(results),
                           file_name='article_search_results.csv', mime='text/csv')
    with col2:
        if count_pdf and Path(st.session_state['paper_finder_zip']).exists():
            with open(st.session_state['paper_finder_zip'], 'rb') as f:
                st.download_button(f'⬇️ Download {count_pdf} PDFs (ZIP)', data=f,
                                   file_name='downloaded_papers.zip', mime='application/zip')

    if count_pdf:
        with st.expander('Download an individual PDF'):
            downloads = [r for r in results if r.get('File') and Path(r['File']).is_file()]
            selected = st.selectbox('Saved paper', range(len(downloads)),
                                    format_func=lambda i: f"{downloads[i]['ID']} — {downloads[i]['Input title'][:110]}")
            chosen = downloads[selected]
            with open(chosen['File'], 'rb') as pdf:
                st.download_button('Download selected PDF', data=pdf,
                                   file_name=Path(chosen['File']).name, mime='application/pdf')

    api_errors = [f"ID {r['ID']}: {r['API notes']}" for r in results if r.get('API notes')]
    if api_errors:
        with st.expander(f'API errors / limits ({len(api_errors)} records)'):
            st.text('\n'.join(api_errors))

st.caption('Sources: OpenAlex, Europe PMC, Semantic Scholar, Crossref. No screening decisions or original Excel fields are changed.')

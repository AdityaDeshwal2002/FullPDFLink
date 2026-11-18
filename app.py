"""Launch with: streamlit run app.py"""
from pathlib import Path
import random

import requests
import streamlit as st

from paper_finder import find_one, load_sheets, make_zip, results_csv
from project_store import ProjectStore


EMOJIS = ['📚', '🔬', '🧪', '📄', '🧠', '🌱', '🔎', '💡']
DATA_DIR = Path(__file__).resolve().parent / 'local_data'
store = ProjectStore(DATA_DIR)

st.set_page_config(page_title='Research PDF Finder', page_icon='📄', layout='wide')
if 'recovered_runs' not in st.session_state:
    store.recover_interrupted()
    st.session_state['recovered_runs'] = True


def run_search(project: dict, items: list[tuple[str, str]]) -> None:
    project_id = project['id']
    token = store.begin_run(project_id, len(items))
    progress = st.progress(0, text='Searching for articles…')
    session = requests.Session()
    session.headers.update({'User-Agent': 'ResearchPDF-Finder/1.0 (academic article discovery)'})
    try:
        for index, (identifier, title) in enumerate(items, 1):
            progress.progress((index - 1) / len(items), text=f'Study {index}/{len(items)}: {title[:76]}')
            result = find_one(
                title, identifier, store.pdf_folder(project_id), session,
                openalex_key=st.session_state.get('openalex_key', '').strip(),
                semantic_key=st.session_state.get('semantic_key', '').strip(),
                email=st.session_state.get('contact_email', '').strip(),
            )
            store.add_result(project_id, token, result)
            progress.progress(index / len(items), text=f'Study {index}/{len(items)} finished')
        make_zip(store.get(project_id)['results'], store.zip_path(project_id))
        store.finish_run(project_id, token)
        progress.progress(1.0, text='Search finished')
        st.rerun()
    except Exception as exc:
        # Request exceptions may contain API keys in URLs, so keep only the error type.
        store.interrupt_run(project_id, token, type(exc).__name__)
        st.error(f'Run interrupted ({type(exc).__name__}). Reopen the project to retry.')
    finally:
        session.close()


def show_results(project: dict) -> None:
    results = project['results']
    if not results:
        return
    count_pdf = sum(row['Result'] == 'PDF downloaded' for row in results)
    count_links = sum(bool(row['Article link'] or row['PDF link']) for row in results)
    a, b, c = st.columns(3)
    a.metric('Titles searched', len(results))
    b.metric('Articles / links found', count_links)
    c.metric('PDFs downloaded', count_pdf)

    st.subheader('Results')
    columns = ('ID', 'Input title', 'Matched title', 'Match', 'Source',
               'Article link', 'PDF link', 'Result')
    st.dataframe(
        [{key: row.get(key, '') for key in columns} for row in results],
        column_config={
            'Article link': st.column_config.LinkColumn('Article link', display_text='Open article'),
            'PDF link': st.column_config.LinkColumn('PDF link', display_text='Open PDF'),
        }, use_container_width=True, hide_index=True, height=420,
    )
    st.caption('Close title matches should be checked manually. Only verified PDFs are saved.')

    left, right = st.columns(2)
    left.download_button('⬇️ Download results CSV', data=results_csv(results),
                         file_name='article_search_results.csv', mime='text/csv')
    if count_pdf:
        zip_path = store.zip_path(project['id'])
        if not zip_path.exists():
            make_zip(results, zip_path)
        right.download_button(f'⬇️ Download {count_pdf} PDFs (ZIP)', data=zip_path.read_bytes(),
                              file_name='downloaded_papers.zip', mime='application/zip')
        with st.expander('Download an individual PDF'):
            folder = store.pdf_folder(project['id']).resolve()
            downloads = []
            for row in results:
                path = Path(row.get('File') or '')
                if path.is_file() and path.resolve().parent == folder:
                    downloads.append(row)
            if downloads:
                selected = st.selectbox('Saved paper', range(len(downloads)),
                                        format_func=lambda i: f"{downloads[i]['ID']} — {downloads[i]['Input title'][:110]}")
                chosen = downloads[selected]
                path = Path(chosen['File'])
                st.download_button('Download selected PDF', data=path.read_bytes(),
                                   file_name=path.name, mime='application/pdf')

    api_errors = [f"ID {row['ID']}: {row['API notes']}" for row in results if row.get('API notes')]
    if api_errors:
        with st.expander(f'API errors / limits ({len(api_errors)} records)'):
            st.text('\n'.join(api_errors))


projects = store.list_projects()
if st.session_state.get('project_id') not in {project['id'] for project in projects}:
    st.session_state['project_id'] = projects[0]['id'] if projects else None
if 'view' not in st.session_state:
    st.session_state['view'] = 'project'

with st.sidebar:
    st.header('📄 Research PDF Finder')
    if st.button('＋ New project', use_container_width=True):
        st.session_state['project_id'] = store.create('Untitled project', random.choice(EMOJIS))
        st.session_state['view'] = 'project'
        st.rerun()
    st.caption('Projects')
    with st.container(height=420):
        for item in projects:
            active = st.session_state['view'] == 'project' and st.session_state['project_id'] == item['id']
            label = f"{item['emoji']} {item['name'][:28]}"
            if st.button(label, key=f"project_{item['id']}", use_container_width=True,
                         type='primary' if active else 'secondary'):
                st.session_state['project_id'] = item['id']
                st.session_state['view'] = 'project'
                st.rerun()
    st.divider()
    if st.button('⚙️ Settings', use_container_width=True,
                 type='primary' if st.session_state['view'] == 'settings' else 'secondary'):
        st.session_state['view'] = 'settings'
        st.rerun()

if st.session_state['view'] == 'settings':
    st.title('Settings')
    st.caption('These values stay in this browser session only. Enter them again after closing it.')
    st.session_state['openalex_key'] = st.text_input(
        'OpenAlex API key', value=st.session_state.get('openalex_key', ''),
        type='password', key='openalex_key_input',
        help='Recommended for larger batches and OpenAlex-hosted PDFs.',
    )
    st.session_state['semantic_key'] = st.text_input(
        'Semantic Scholar API key', value=st.session_state.get('semantic_key', ''),
        type='password', key='semantic_key_input', help='Optional. Improves API access.',
    )
    st.session_state['contact_email'] = st.text_input(
        'Contact email (for Crossref)', value=st.session_state.get('contact_email', ''),
        placeholder='you@example.com', key='contact_email_input',
    )
    st.stop()

project_id = st.session_state['project_id']
if project_id is None:
    st.title('Your projects')
    st.info('Create a project to upload a spreadsheet and find articles and PDFs.')
    st.stop()

project = store.get(project_id)
st.title(f"{project['emoji']} {project['name']}")
st.caption(f"Status: {project['status'].capitalize()}")

with st.expander('Project details'):
    with st.form(f'rename_{project_id}'):
        name = st.text_input('Project name', value=project['name'])
        emoji = st.text_input('Emoji', value=project['emoji'], max_chars=16)
        if st.form_submit_button('Save name and emoji'):
            try:
                store.rename(project_id, name, emoji or random.choice(EMOJIS))
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    confirm = st.checkbox('I understand this permanently removes the project and its files',
                          key=f'delete_confirm_{project_id}')
    if st.button('Delete project', disabled=not confirm, key=f'delete_{project_id}'):
        store.delete(project_id)
        st.session_state['project_id'] = None
        st.rerun()

if project['status'] == 'interrupted':
    st.warning('The previous run was interrupted. You can retry with the same spreadsheet.')
if project['error']:
    st.caption(f"Last run error: {project['error']}")

saved_data = None
if project['input_file']:
    try:
        saved_data = store.input_path(project).read_bytes()
    except OSError as exc:
        st.error(f'Cannot read the saved spreadsheet: {exc}')
        st.stop()
    st.write(f"**Spreadsheet:** {project['filename']}")
    st.download_button('Download original spreadsheet', data=saved_data,
                       file_name=project['filename'])

upload = None
if project['status'] == 'draft':
    upload = st.file_uploader('Upload or replace a CSV/XLSX file', type=['xlsx', 'csv'],
                              key=f'upload_{project_id}')

data = upload.getvalue() if upload else saved_data
filename = upload.name if upload else project['filename']
if data is None:
    st.info('Upload a spreadsheet to prepare this project.')
    st.stop()

try:
    sheets = load_sheets(data, filename)
except Exception as exc:
    st.error(f'Cannot read the spreadsheet: {exc}')
    st.stop()

if not sheets:
    st.warning('No worksheets were found.')
    st.stop()

if project['status'] == 'draft':
    names = list(sheets)
    default_sheet = 'Studies Export' if 'Studies Export' in names else names[0]
    if project['sheet'] in names and not upload:
        default_sheet = project['sheet']
    selected_sheet = st.selectbox('Worksheet', names, index=names.index(default_sheet),
                                  key=f'sheet_{project_id}')
else:
    selected_sheet = project['sheet']
    st.write(f"**Worksheet:** {selected_sheet} · **Title column:** {project['title_column']}")

records = sheets.get(selected_sheet, [])
if not records:
    st.warning('This worksheet has no data rows.')
    st.stop()

columns = list(records[0])
if any(not isinstance(col, str) or not col.strip() for col in columns):
    st.error('The spreadsheet needs a nonempty header for every column.')
    st.stop()
if project['status'] == 'draft':
    title_matches = [col for col in columns if col.casefold().strip() == 'title']
    default_title = title_matches[0] if title_matches else columns[0]
    if project['title_column'] in columns and not upload:
        default_title = project['title_column']
    title_col = st.selectbox('Title column', columns, index=columns.index(default_title),
                              key=f'title_{project_id}')
else:
    title_col = project['title_column']

id_matches = [col for col in columns if col.casefold().strip() == 'id']
id_col = id_matches[0] if id_matches else None
items = []
for index, row in enumerate(records, 1):
    title = str(row.get(title_col) or '').strip()
    if title:
        identifier = str(row.get(id_col) or index) if id_col else str(index)
        items.append((identifier, title))

st.write(f'**{len(items)} titles ready to search.**')
with st.expander('Preview the titles'):
    st.dataframe([{'ID': identifier, 'Title': title} for identifier, title in items],
                 use_container_width=True, hide_index=True)

if project['status'] == 'draft':
    pending = (data != saved_data or filename != project['filename'] or
               selected_sheet != project['sheet'] or title_col != project['title_column'])
    if pending:
        if st.button('Save spreadsheet and selection', disabled=not items):
            try:
                store.save_upload(project_id, data, filename, selected_sheet, title_col)
                st.rerun()
            except (OSError, ValueError) as exc:
                st.error(str(exc))
        st.info('Save the spreadsheet and selection before starting the search.')
    elif st.button('🔎 Find article links and PDFs', type='primary', disabled=not items):
        run_search(project, items)
elif project['status'] == 'interrupted':
    st.write(f"Previous run: {project['completed_count']}/{project['total_count']} titles processed.")
    if st.button('Retry search with this spreadsheet', type='primary', disabled=not items):
        run_search(project, items)

show_results(project)
st.caption('Sources: OpenAlex, Europe PMC, Semantic Scholar, Crossref. The original spreadsheet is not edited.')

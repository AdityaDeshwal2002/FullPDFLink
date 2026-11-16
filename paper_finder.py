"""Small, title-only scholarly discovery and open-PDF retrieval module.

No input spreadsheet fields are edited or reclassified.
"""
from __future__ import annotations

import csv
import io
import os
import posixpath
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import requests

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "p": "http://schemas.openxmlformats.org/package/2006/relationships"}


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref.upper())
    if not letters:
        return 0
    n = 0
    for letter in letters.group():
        n = n * 26 + ord(letter) - ord('A') + 1
    return n - 1


def load_sheets(data: bytes, filename: str) -> dict[str, list[dict[str, str]]]:
    """Read simple .xlsx or .csv data using the Python standard library."""
    if filename.lower().endswith('.csv'):
        text = data.decode('utf-8-sig', errors='replace')
        return {'CSV': list(csv.DictReader(io.StringIO(text)))}
    if not filename.lower().endswith('.xlsx'):
        raise ValueError('Please upload an .xlsx or .csv file.')

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = set(z.namelist())
        root = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        target_by_id = {item.get('Id'): item.get('Target') for item in rels}
        shared: list[str] = []
        if 'xl/sharedStrings.xml' in names:
            texts = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for item in texts.findall('m:si', NS):
                shared.append(''.join(t.text or '' for t in item.findall('.//m:t', NS)))

        sheets: dict[str, list[dict[str, str]]] = {}
        for item in root.findall('m:sheets/m:sheet', NS):
            sheet_name = item.get('name', 'Sheet')
            rid = item.get(f'{{{NS["r"]}}}id')
            target = target_by_id.get(rid, '')
            if target.startswith('/'):
                sheet_path = target.lstrip('/')
            else:
                sheet_path = posixpath.normpath(posixpath.join('xl', target))
            if sheet_path not in names:
                continue
            xml = ET.fromstring(z.read(sheet_path))
            raw_rows: list[list[str]] = []
            for row in xml.findall('m:sheetData/m:row', NS):
                cells: dict[int, str] = {}
                for c in row.findall('m:c', NS):
                    index = _column_index(c.get('r', 'A1'))
                    kind = c.get('t', '')
                    value = c.find('m:v', NS)
                    if kind == 's' and value is not None:
                        try:
                            content = shared[int(value.text or 0)]
                        except (ValueError, IndexError):
                            content = ''
                    elif kind == 'inlineStr':
                        content = ''.join(t.text or '' for t in c.findall('.//m:t', NS))
                    elif value is not None:
                        content = value.text or ''
                    else:
                        content = ''
                    cells[index] = content.strip()
                if cells:
                    width = max(cells) + 1
                    raw_rows.append([cells.get(i, '') for i in range(width)])
            if not raw_rows:
                sheets[sheet_name] = []
                continue
            headers = [h or f'Column {i+1}' for i, h in enumerate(raw_rows[0])]
            results: list[dict[str, str]] = []
            for row in raw_rows[1:]:
                if not any(row):
                    continue
                results.append({key: row[i] if i < len(row) else '' for i, key in enumerate(headers)})
            sheets[sheet_name] = results
        return sheets


def normalize_title(text: str) -> str:
    normalized = unicodedata.normalize('NFKD', text or '')
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', normalized.casefold()))


def title_score(a: str, b: str) -> float:
    a, b = normalize_title(a), normalize_title(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def safe_url(url: str | None) -> str:
    if not isinstance(url, str):
        return ''
    p = urlparse(url.strip())
    return url.strip() if p.scheme in ('http', 'https') and p.netloc else ''


def _fetch_json(session: requests.Session, url: str, params: dict | None = None,
                headers: dict | None = None) -> dict:
    response = session.get(url, params=params, headers=headers, timeout=(5, 13))
    if response.status_code == 404:
        return {}
    if response.status_code == 429:
        raise RuntimeError(f'Rate limited by {urlparse(url).netloc} (HTTP 429)')
    response.raise_for_status()
    return response.json()


def _candidate(title: str, source: str, found_title: str, article: str,
               pdfs: list[str] | None = None, auth_pdf: str = '') -> dict:
    return {
        'source': source,
        'found_title': found_title or '',
        'article_url': safe_url(article),
        'pdf_urls': list(dict.fromkeys(u for u in (safe_url(x) for x in (pdfs or [])) if u)),
        'auth_pdf': safe_url(auth_pdf),
        'score': title_score(title, found_title),
    }


def search_openalex(session: requests.Session, title: str, api_key: str = '') -> list[dict]:
    params: dict[str, Any] = {'search.title': title, 'per_page': 6}
    if api_key:
        params['api_key'] = api_key
    data = _fetch_json(session, 'https://api.openalex.org/works', params=params)
    if not data.get('results') and len(title.split()) > 12:
        params['search.title'] = ' '.join(title.split()[:11])
        data = _fetch_json(session, 'https://api.openalex.org/works', params=params)
    results = []
    for work in data.get('results', []):
        found_title = work.get('display_name') or work.get('title') or ''
        best = work.get('best_oa_location') or {}
        main = work.get('primary_location') or {}
        location_pdfs = [best.get('pdf_url'), main.get('pdf_url')]
        for location in (work.get('locations') or [])[:15]:
            if location.get('is_oa'):
                location_pdfs.append(location.get('pdf_url'))
        content_pdf = (work.get('content_urls') or {}).get('pdf') if api_key else ''
        article = (best.get('landing_page_url') or main.get('landing_page_url')
                   or work.get('doi') or work.get('id') or '')
        results.append(_candidate(title, 'OpenAlex', found_title, article,
                                  [u for u in location_pdfs if u], content_pdf or ''))
    return results


def search_semantic_scholar(session: requests.Session, title: str,
                            api_key: str = '') -> list[dict]:
    fields = 'title,url,openAccessPdf'
    headers = {'x-api-key': api_key} if api_key else None
    data = _fetch_json(session, 'https://api.semanticscholar.org/graph/v1/paper/search',
                       {'query': title, 'limit': 5, 'fields': fields}, headers=headers)
    results = []
    for paper in data.get('data') or []:
        pdf = (paper.get('openAccessPdf') or {}).get('url')
        results.append(_candidate(title, 'Semantic Scholar', paper.get('title', ''),
                                  paper.get('url', ''), [pdf] if pdf else []))
    return results


def search_europe_pmc(session: requests.Session, title: str) -> list[dict]:
    phrase = ' '.join(title.replace('"', '').split()[:9])
    data = _fetch_json(session, 'https://www.ebi.ac.uk/europepmc/webservices/rest/search',
                       {'query': f'TITLE:"{phrase}"', 'pageSize': 5,
                        'resultType': 'core', 'format': 'json'})
    results = []
    for paper in (data.get('resultList') or {}).get('result') or []:
        pmcid = paper.get('pmcid', '')
        article = (f'https://europepmc.org/articles/{pmcid}' if pmcid else
                   f'https://europepmc.org/article/{paper.get("source", "MED")}/{paper.get("id", "")}')
        links = (paper.get('fullTextUrlList') or {}).get('fullTextUrl') or []
        pdf_links = []
        if paper.get('isOpenAccess') == 'Y':
            pdf_links = [l.get('url') for l in links
                         if (l.get('documentStyle') or '').lower() == 'pdf']
            if not pdf_links and pmcid:
                # The landing page remains available when a PDF location isn't provided.
                pass
        results.append(_candidate(title, 'Europe PMC', paper.get('title', ''), article,
                                  [u for u in pdf_links if u]))
    return results


def search_crossref(session: requests.Session, title: str, email: str = '') -> list[dict]:
    headers = {'User-Agent': f'ResearchPDF-Finder/1.0 (mailto:{email})'} if email else None
    data = _fetch_json(session, 'https://api.crossref.org/works',
                       {'query.bibliographic': title, 'rows': 5}, headers=headers)
    results = []
    for item in (data.get('message') or {}).get('items') or []:
        names = item.get('title') or []
        name = names[0] if names else ''
        # Crossref's PDF content links often require subscriptions; use its article link only.
        results.append(_candidate(title, 'Crossref', name, item.get('URL', ''), []))
    return results


def _safe_filename(identifier: str, title: str) -> str:
    slug = normalize_title(title).replace(' ', '_')[:74] or 'article'
    id_part = re.sub(r'[^a-zA-Z0-9_-]', '_', identifier)[:24] or 'study'
    return f'{id_part}_{slug}.pdf'


def download_pdf(session: requests.Session, url: str, destination: Path,
                 api_key: str = '', max_bytes: int = 45 * 1024 * 1024) -> bool:
    url = safe_url(url)
    if not url:
        return False
    # Only send the optional credential to OpenAlex's own PDF service.
    params = {'api_key': api_key} if api_key and urlparse(url).hostname == 'content.openalex.org' else None
    valid = False
    try:
        with session.get(url, params=params, stream=True, timeout=(6, 25),
                         headers={'Accept': 'application/pdf'}) as response:
            response.raise_for_status()
            content_length = int(response.headers.get('content-length', '0') or 0)
            if content_length > max_bytes:
                return False
            count = 0
            with open(destination, 'wb') as fp:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        count += len(chunk)
                        if count > max_bytes:
                            raise ValueError('PDF exceeds file size limit')
                        fp.write(chunk)
        if destination.stat().st_size < 150:
            return False
        with open(destination, 'rb') as fp:
            if b'%PDF-' not in fp.read(1024):
                return False
        valid = True
        return True
    except (requests.RequestException, OSError, ValueError):
        return False
    finally:
        if not valid:
            destination.unlink(missing_ok=True)


def find_one(title: str, identifier: str, folder: Path, session: requests.Session,
             openalex_key: str = '', semantic_key: str = '', email: str = '') -> dict:
    """Search titles, collect links, and download *only* strong title matches."""
    searches: list[tuple[str, Callable[[], list[dict]]]] = [
        ('OpenAlex', lambda: search_openalex(session, title, openalex_key)),
        ('Europe PMC', lambda: search_europe_pmc(session, title)),
        ('Semantic Scholar', lambda: search_semantic_scholar(session, title, semantic_key)),
        ('Crossref', lambda: search_crossref(session, title, email)),
    ]
    found: list[dict] = []
    errors: list[str] = []
    saved_path = ''
    downloaded_from = ''
    downloaded_url = ''
    attempted: set[str] = set()
    for name, search_fn in searches:
        try:
            candidates = search_fn()
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors.append(f'{name}: {exc}')
            continue
        for candidate in candidates:
            if candidate['score'] >= 0.74:
                found.append(candidate)
        for candidate in sorted(candidates, key=lambda x: x['score'], reverse=True):
            if candidate['score'] < 0.88:
                continue
            destination = folder / _safe_filename(identifier, title)
            pdf_urls = list(candidate['pdf_urls'])
            if candidate['auth_pdf'] and openalex_key:
                pdf_urls.append(candidate['auth_pdf'])
            for pdf in pdf_urls:
                if pdf in attempted:
                    continue
                attempted.add(pdf)
                if download_pdf(session, pdf, destination, openalex_key):
                    saved_path = str(destination)
                    downloaded_from = candidate['source']
                    downloaded_url = pdf
                    break
            if saved_path:
                break
        if saved_path:
            break
        # If OpenAlex already supplied article links, Crossref usually adds no PDF value.
        if name == 'Semantic Scholar' and found:
            break

    found.sort(key=lambda x: x['score'], reverse=True)
    best = found[0] if found else None
    pdf_candidate = next((c for c in found if c['pdf_urls']), None)
    # OpenAlex cached downloads need a private API key; don't expose that key in a clickable URL.
    pdf_link = (downloaded_url if downloaded_url and urlparse(downloaded_url).hostname != 'content.openalex.org'
                else (pdf_candidate['pdf_urls'][0] if pdf_candidate else ''))
    return {
        'ID': identifier,
        'Input title': title,
        'Matched title': best['found_title'] if best else '',
        'Match': f'{best["score"]:.0%}' if best else '',
        'Source': downloaded_from or (best['source'] if best else ''),
        'Article link': (best['article_url'] if best else ''),
        'PDF link': pdf_link,
        'Result': ('PDF downloaded' if saved_path else 'PDF link found' if pdf_link
                   else 'Article link found' if best and best['article_url']
                   else 'No confident match'),
        'File': saved_path,
        'API notes': '; '.join(errors),
    }


def results_csv(results: list[dict]) -> bytes:
    columns = ['ID', 'Input title', 'Matched title', 'Match', 'Source',
               'Article link', 'PDF link', 'Result', 'API notes']
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(results)
    return output.getvalue().encode('utf-8-sig')


def make_zip(results: list[dict], destination: Path) -> int:
    count = 0
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as z:
        for row in results:
            path = row.get('File', '')
            if path and Path(path).is_file():
                z.write(path, arcname=Path(path).name)
                count += 1
    return count

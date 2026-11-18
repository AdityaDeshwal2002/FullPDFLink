"""Basic offline checks. Run: python test_paper_finder.py SAMPLE_FILE.xlsx"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import requests

from paper_finder import _candidate, find_one, load_sheets, make_zip, title_score


class PaperFinderTests(unittest.TestCase):
    def test_title_normalization(self):
        self.assertGreater(title_score('EQ-5D: Quality-of-Life', 'EQ 5D quality of life'), .95)
        self.assertLess(title_score('Kidney disease in children', 'Smoking trends in Europe'), .6)

    def test_load_uploaded_sample(self):
        if len(sys.argv) > 1 and sys.argv[1].endswith('.xlsx'):
            sample = Path(sys.argv[1])
            sheets = load_sheets(sample.read_bytes(), sample.name)
            self.assertIn('Studies Export', sheets)
            self.assertEqual(len(sheets['Studies Export']), 14)
            self.assertEqual(len([x for x in sheets['Studies Export'] if x['Title']]), 14)

    def test_no_false_download_for_unrelated_title(self):
        title = 'Real world survival among trial participants'
        unrelated = [_candidate(title, 'OpenAlex', 'The history of chemistry',
                                'https://example.com/article', ['https://example.com/file.pdf'])]
        with tempfile.TemporaryDirectory() as tmp:
            with patch('paper_finder.search_openalex', return_value=unrelated), \
                 patch('paper_finder.search_europe_pmc', return_value=[]), \
                 patch('paper_finder.search_semantic_scholar', return_value=[]), \
                 patch('paper_finder.search_crossref', return_value=[]), \
                 patch('paper_finder.download_pdf') as download:
                result = find_one(title, '1', Path(tmp), None)
                self.assertEqual(result['Result'], 'No confident match')
                download.assert_not_called()

    def test_successful_download_and_zip(self):
        title = 'My Test Research Paper'
        matched = [_candidate(title, 'OpenAlex', title, 'https://example.com/paper',
                              ['https://example.com/test.pdf'])]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            def fake_download(sess, url, dest, key=''):
                dest.write_bytes(b'%PDF-1.4\n'+b'a'*250)
                return True
            with patch('paper_finder.search_openalex', return_value=matched), \
                 patch('paper_finder.download_pdf', side_effect=fake_download):
                row = find_one(title, 'ST-01', out, None)
            self.assertEqual(row['Result'], 'PDF downloaded')
            self.assertEqual(row['PDF link'], 'https://example.com/test.pdf')
            self.assertEqual(make_zip([row], out / 'all.zip'), 1)

    def test_api_key_is_not_saved_in_error_notes(self):
        response = requests.Response()
        response.status_code = 401
        response.url = 'https://example.com/?api_key=secret'
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch('paper_finder.search_openalex',
                      side_effect=requests.HTTPError('https://example.com/?api_key=secret', response=response)),
                patch('paper_finder.search_europe_pmc', return_value=[]),
                patch('paper_finder.search_semantic_scholar', return_value=[]),
                patch('paper_finder.search_crossref', return_value=[]),
            ):
                result = find_one('A paper', '1', Path(tmp), None, openalex_key='secret')
            self.assertNotIn('secret', result['API notes'])
            self.assertIn('HTTP 401', result['API notes'])


if __name__ == '__main__':
    # Prevent unittest from reading optional sample path as a test label.
    if len(sys.argv) > 1 and sys.argv[1].endswith('.xlsx'):
        sample = sys.argv[1]
        sys.argv = [sys.argv[0]]
        import builtins
        builtins._TEST_SAMPLE_PATH = sample
        PaperFinderTests.test_load_uploaded_sample = (lambda self: self.assertEqual(
            len(load_sheets(Path(sample).read_bytes(), Path(sample).name)['Studies Export']), 14))
    unittest.main()

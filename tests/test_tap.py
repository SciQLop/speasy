import unittest
from unittest import mock

from speasy.core import tap
from speasy.core.tap import TapError

CSA_TAP = "https://csa.esac.esa.int/csa-sl-tap/tap/"

_VOTABLE_ERROR = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.2" xmlns="http://www.ivoa.net/xml/VOTable/v1.2">
<RESOURCE type="results">
<INFO name="QUERY_STATUS" value="ERROR">Cannot parse query: 1 unresolved identifiers: nope</INFO>
</RESOURCE>
</VOTABLE>"""


class _Response:
    def __init__(self, status_code, text):
        self.status_code, self.text = status_code, text
        self.ok = status_code == 200


class Query(unittest.TestCase):
    def test_rows_are_dicts_keyed_by_column_name(self):
        rows = tap.query(CSA_TAP, "SELECT TOP 2 * FROM csa.v_mission")
        self.assertEqual(len(rows), 2)
        self.assertIn('name', rows[0])

    def test_large_results_are_complete(self):
        # the synchronous endpoint must not truncate: CSA has thousands of parameters
        count = tap.query(CSA_TAP, "SELECT count(*) AS n FROM csa.v_parameter")[0]['n']
        rows = tap.query(CSA_TAP, "SELECT parameter_id FROM csa.v_parameter")
        self.assertGreater(count, 2000)
        self.assertEqual(len(rows), count)

    def test_a_refused_query_says_why(self):
        with self.assertRaisesRegex(TapError, "unresolved identifiers"):
            tap.query(CSA_TAP, "SELECT nope FROM csa.v_mission")


class ErrorReporting(unittest.TestCase):
    def _query_answering(self, status_code, text):
        with mock.patch.object(tap.http, 'get', return_value=_Response(status_code, text)):
            return tap.query(CSA_TAP, "SELECT nope FROM csa.v_mission")

    def test_an_error_votable_sent_with_http_200_is_an_error(self):
        with self.assertRaisesRegex(TapError, "csa.esac.esa.int.*unresolved identifiers: nope"):
            self._query_answering(200, _VOTABLE_ERROR)

    def test_an_error_without_a_votable_gives_the_http_status(self):
        with self.assertRaisesRegex(TapError, "HTTP 503"):
            self._query_answering(503, "<html>Service Unavailable</html>")


if __name__ == '__main__':
    unittest.main()

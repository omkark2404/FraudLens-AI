import unittest
import datetime
from services.extraction_service import _parse_date, _regex_extract

class TestExtractionService(unittest.TestCase):

    def test_parse_date_formats(self):
        self.assertEqual(_parse_date("01/12/2020"), datetime.date(2020, 12, 1))
        self.assertEqual(_parse_date("2020-12-01"), datetime.date(2020, 12, 1))
        self.assertEqual(_parse_date("12-01-2020"), datetime.date(2020, 1, 12)) # Note: %m-%d-%Y is before %d-%m-%Y in list if ambiguity, wait let's check code. Actually it will just match the first working format.
        
    def test_regex_extract_dates(self):
        full_text = "DOB: 12/05/1980 ISS: 01/01/2020 EXP: 01/01/2030 LIC: D1234567"
        values = {"dob": None, "issue_date": None, "expiry_date": None, "license_number": None}
        confidences = {"dob": None, "issue_date": None, "expiry_date": None, "license_number": None}
        
        updated_values, _ = _regex_extract(full_text, values, confidences)
        
        self.assertIsNotNone(updated_values["dob"])
        self.assertIsNotNone(updated_values["issue_date"])
        self.assertIsNotNone(updated_values["expiry_date"])
        self.assertEqual(updated_values["license_number"], "D1234567")

if __name__ == '__main__':
    unittest.main()

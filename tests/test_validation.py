import datetime
import unittest

from models.schemas import ExtractedFields, OCRBlock
from services.validation_service import compute_validation_score, evaluate_verdict


class TestValidationService(unittest.TestCase):
    def test_compute_validation_score_perfect(self):
        # Setup perfect fields
        future_date = (datetime.date.today() + datetime.timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
        fields = ExtractedFields(
            name="JOHN DOE",
            dob="1990-01-01",
            issue_date="2020-01-01",
            expiry_date=future_date,
            license_number="A1234567",
        )

        # High confidence block
        blocks = [OCRBlock(text="TEST", bbox=[0, 0, 10, 10], confidence=0.9)]

        result = compute_validation_score(fields, blocks, doc_type="license")

        # 20 (name) + 15 (age>=16) + 10 (issue>dob) + 15 (expiry>issue) + 15 (future) + 5 (unverified format) + 15 (conf) = 95
        self.assertEqual(result.score, 95)

    def test_compute_validation_score_missing(self):
        fields = ExtractedFields()
        blocks = [OCRBlock(text="TEST", bbox=[0, 0, 10, 10], confidence=0.4)]

        result = compute_validation_score(fields, blocks, doc_type="license")
        self.assertEqual(result.score, 0)

    def test_evaluate_verdict_missing_fields(self):
        fields = ExtractedFields(name=None, license_number=None)
        # Low confidence + missing fields = quality issues
        blocks = [OCRBlock(text="TEST", bbox=[0, 0, 10, 10], confidence=0.3)]

        validation = compute_validation_score(fields, blocks, doc_type="license")
        result = evaluate_verdict(blocks, fields, validation, doc_type="license")
        # Validation score is < 50, so it will be rejected due to low score, plus missing fields and low conf
        self.assertEqual(result.verdict, "rejected")
        self.assertTrue(
            any("missing critical fields" in anomaly for anomaly in result.reasons)
        )
        self.assertTrue(
            any("low OCR confidence" in anomaly for anomaly in result.reasons)
        )
        self.assertTrue(
            any("validation score too low" in anomaly for anomaly in result.reasons)
        )

    def test_evaluate_verdict_quality(self):
        future_date = (datetime.date.today() + datetime.timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
        fields = ExtractedFields(
            name="JOHN DOE",
            dob="1990-01-01",
            issue_date="2020-01-01",
            expiry_date=future_date,
            license_number="A1234567",
        )
        blocks = [OCRBlock(text="TEST", bbox=[0, 0, 10, 10], confidence=0.3)]

        validation = compute_validation_score(
            fields, blocks, doc_type="license"
        )  # Score 80
        result = evaluate_verdict(blocks, fields, validation, doc_type="license")
        # Should be flagged for low confidence -> needs_better_image
        self.assertEqual(result.verdict, "needs_better_image")
        self.assertTrue(
            any("low OCR confidence" in anomaly for anomaly in result.reasons)
        )


if __name__ == "__main__":
    unittest.main()

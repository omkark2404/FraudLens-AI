import unittest
import datetime
from models.schemas import OCRBlock, ExtractedFields
from services.validation_service import compute_validation_score, detect_fraud
from core.config import config

class TestValidationService(unittest.TestCase):

    def test_compute_validation_score_perfect(self):
        # Setup perfect fields
        future_date = (datetime.date.today() + datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        fields = ExtractedFields(
            name="JOHN DOE",
            dob="1990-01-01",
            issue_date="2020-01-01",
            expiry_date=future_date,
            license_number="A1234567"
        )
        
        # High confidence block
        blocks = [OCRBlock(text="TEST", bbox=[0,0,10,10], confidence=0.9)]
        
        result = compute_validation_score(fields, blocks)
        
        # 20 + 15 + 15 + 15 + 10 + 10 + 15 = 100
        self.assertEqual(result.score, 100)

    def test_compute_validation_score_missing(self):
        fields = ExtractedFields()
        blocks = [OCRBlock(text="TEST", bbox=[0,0,10,10], confidence=0.4)]
        
        result = compute_validation_score(fields, blocks)
        self.assertEqual(result.score, 0)

    def test_detect_fraud_missing_fields(self):
        fields = ExtractedFields(name=None, license_number=None)
        blocks = [OCRBlock(text="TEST", bbox=[0,0,10,10], confidence=0.9)]
        
        result = detect_fraud(blocks, fields)
        self.assertEqual(result.status, "Suspicious")
        self.assertTrue(any("missing critical fields" in anomaly for anomaly in result.flags))

    def test_detect_fraud_low_confidence(self):
        fields = ExtractedFields(name="JOHN", license_number="A123")
        blocks = [OCRBlock(text="TEST", bbox=[0,0,10,10], confidence=0.3)]
        
        result = detect_fraud(blocks, fields)
        # Should be flagged for low confidence
        self.assertTrue(any("low OCR confidence" in anomaly for anomaly in result.flags))

if __name__ == '__main__':
    unittest.main()

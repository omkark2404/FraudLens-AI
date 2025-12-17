import os
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = "fixtures/synthetic"

def create_image(filename, lines, fraudulent=False):
    img = Image.new('RGB', (800, 500), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # We rely on default font for simplicity
    font = ImageFont.load_default()
    
    y = 50
    for line in lines:
        if fraudulent and "overlap" in line.lower():
            # Draw overlapping text
            d.text((100, y), line, fill=(0, 0, 0))
            d.text((100, y+5), line, fill=(255, 0, 0))
        else:
            d.text((100, y), line, fill=(0, 0, 0))
        y += 50
        
    img.save(os.path.join(OUTPUT_DIR, filename))

def generate_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating synthetic driver's licenses...")
    
    # 5 Valid Licenses
    for i in range(1, 6):
        create_image(f"valid_dl_{i}.png", [
            "DRIVER LICENSE",
            f"NAME: JOHN DOE {i}",
            "DOB: 1990-01-01",
            "ISS: 2020-01-01",
            "EXP: 2030-01-01",
            f"LIC: A123456{i}"
        ])
        
    # 5 Fraud/Poor Quality Licenses
    for i in range(1, 6):
        create_image(f"fraud_dl_{i}.png", [
            "DRIVER LICENSE",
            f"NAME: JANE DOE {i}",
            "DOB: 1990-01-01",
            "ISS: 2020-01-01",
            "EXP: 2018-01-01", # Expired
            f"LIC: X99", # Invalid format
            "overlap overlap overlap" # Will trigger overlap fraud check
        ], fraudulent=True)
        
    print("Generating synthetic insurance cards...")
    
    # 5 Valid Insurance
    for i in range(1, 6):
        create_image(f"valid_ic_{i}.png", [
            "AUTO INSURANCE",
            f"INSURED: JOHN DOE {i}",
            "EFFECTIVE: 2020-01-01",
            "EXPIRES: 2030-01-01",
            f"POLICY NO: POL123456{i}"
        ])
        
    # 5 Fraud/Poor Quality Insurance
    for i in range(1, 6):
        create_image(f"fraud_ic_{i}.png", [
            "AUTO INSURANCE",
            f"INSURED: JANE DOE {i}",
            "EFFECTIVE: 2020-01-01",
            "EXPIRES: 2018-01-01", # Expired
            f"POLICY NO: X",
            "overlap overlap overlap"
        ], fraudulent=True)

    print(f"Generated 20 synthetic documents in {OUTPUT_DIR}")

if __name__ == "__main__":
    generate_all()

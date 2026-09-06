import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def extract_text_from_pdf(file_path):
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
            
        # Fallback to OCR if less than 100 chars extracted (e.g. scanned PDF)
        if len(text.strip()) < 100:
            text = ""
            for page in doc:
                pix = page.get_pixmap()
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text += pytesseract.image_to_string(img)
                
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

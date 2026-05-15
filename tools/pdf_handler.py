import io
import re
from pypdf import PdfReader

def extract_text_from_pdf(pdf_bytes, max_chars=5000):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() for page in reader.pages]
        text = "\n".join(p for p in pages if p)

        # collapse whitespace noise that pypdf leaves behind
        text = re.sub(r'\n{3,}', '\n\n', text)   # 3+ blank lines → 1
        text = re.sub(r'[ \t]{2,}', ' ', text)   # multiple spaces → 1

        return text[:max_chars]

    except Exception as e:
        return f"שגיאה בקריאת ה-PDF: {str(e)}"
    


    
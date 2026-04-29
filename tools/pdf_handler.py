import io
from pypdf import PdfReader

def extract_text_from_pdf(pdf_bytes, max_chars=12000):
    """
    מקבל קובץ PDF (כבייטים) ומחלץ ממנו טקסט.
    מגביל את אורך הטקסט כדי למנוע חריגה ממכסת הטוקנים.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text() + "\n"
        
        return text[:max_chars]
        
    except Exception as e:
        return f"שגיאה בקריאת ה-PDF: {str(e)}"
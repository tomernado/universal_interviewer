# השתמש בגרסה רזה ומהירה של פייתון
FROM python:3.10-slim

# הגדר את תיקיית העבודה בתוך המכולה
WORKDIR /app

# העתק רק את רשימת הספריות קודם (טריק ה-Cache)
COPY requirements.txt .

# התקן את הספריות
RUN pip install --no-cache-dir -r requirements.txt

# העתק את שאר הפרויקט (הקוד והתיקיות) פנימה
COPY . .

# הפקודה שתרוץ כשהמכולה נדלקת
CMD ["python", "main.py"]
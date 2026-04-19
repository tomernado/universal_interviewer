import os
import io
from groq import Groq
from pypdf import PdfReader
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
user_sessions = {}

def extract_text_from_pdf(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# --- פרומפט "מנטור טכני" - דגש על עומק במקרה של חוסר ידע ---
SYSTEM_PROMPT = """
אתה מנטור טכני בכיר. המטרה שלך היא שהמשתמש ילמד את החומר ב-PDF בצורה מעמיקה.
דבר בעברית מקצועית, סבלנית ומלמדת.

חוקי ברזל למבנה (חובה):
1. כל תשובה חייבת לכלול שני חלקים המופרדים על ידי קו מפריד (---).
2. חלק ראשון - למידה והסבר:
   - אם המשתמש צדק: אשר את תשובתו והוסף "ערך מוסף" טכני קצר (טיפ מהשטח או מקרה קצה).
   - אם המשתמש טעה, ענה חלקית או אמר "לא יודע": אל תגיד "לא משנה". כתוב הסבר מעמיק, מפורט ומובנה על המושג. הסבר את ה'למה' ואת ה'איך'. המטרה היא שהוא יבין את הנושא ב-100% לפני שממשיכים.
3. חלק שני - השאלה הבאה:
   - כתוב את הכותרת **השאלה:** (מודגש) ואחריה שאלה אחת חדשה וממוקדת.

חוקי רמזים:
- אם המשתמש לוחץ על רמז: תן רק רמז דק (כיוון מחשבה). אל תיתן את התשובה.
"""

def get_interview_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("רמז 💡", callback_data='hint'), InlineKeyboardButton("דלג שאלה ⏭️", callback_data='skip')],
        [InlineKeyboardButton("סיום וציון משוקלל 📊", callback_data='summary')]
    ])

async def ask_ai(chat_id, user_input):
    session = user_sessions[chat_id]
    session['history'].append({"role": "user", "content": user_input})
    
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile", 
        messages=[{"role": "system", "content": SYSTEM_PROMPT + f"\n\nContext from PDF:\n{session['pdf_text']}"}] + session['history'],
        temperature=0.6,
    )
    
    ai_response = completion.choices[0].message.content
    session['history'].append({"role": "assistant", "content": ai_response})
    return ai_response

async def send_split_message(update: Update, text: str, show_keyboard=False):
    markup = get_interview_keyboard() if show_keyboard else None
    target = update.effective_message
    
    if "---" in text:
        parts = text.split("---", 1)
        await target.reply_text(parts[0].strip(), parse_mode='Markdown')
        await target.reply_text(parts[1].strip(), parse_mode='Markdown', reply_markup=markup)
    else:
        await target.reply_text(text.strip(), parse_mode='Markdown', reply_markup=markup)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text("טוען את חומר הלימוד... 📚")
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        pdf_bytes = await file.download_as_bytearray()
        text = extract_text_from_pdf(pdf_bytes)
        
        user_sessions[chat_id] = {'history': [], 'pdf_text': text}
        response = await ask_ai(chat_id, "התחל בבחינה. בצע סקירה קצרה של הנושאים, שים קו מפריד, ושאל שאלה ראשונה.")
        await send_split_message(update, response, show_keyboard=True)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if chat_id not in user_sessions: return

    if query.data == 'hint':
        response = await ask_ai(chat_id, "תן לי רמז דק מאוד לשאלה. אל תגלה את התשובה ואל תוסיף שאלה חדשה.")
        await query.message.reply_text(f"💡 **רמז:** {response.strip()}", parse_mode='Markdown')
    elif query.data == 'skip':
        response = await ask_ai(chat_id, "דלג על השאלה ועבור לנושא אחר. שים קו מפריד ושאל שאלה חדשה.")
        await send_split_message(update, response, show_keyboard=True)
    elif query.data == 'summary':
        response = await ask_ai(chat_id, "סכם את רמת הידע שלי, תן דגשים לשיפור וציון סופי.")
        await query.message.reply_text(response, parse_mode='Markdown')
        del user_sessions[chat_id]

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions:
        await update.message.reply_text("שלום! כדי להתחיל, שלח לי קובץ PDF.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    try:
        user_text = update.message.text
        if update.message.voice:
            voice_file = await context.bot.get_file(update.message.voice.file_id)
            voice_bytes = await voice_file.download_as_bytearray()
            transcription = client.audio.transcriptions.create(
                file=("audio.ogg", bytes(voice_bytes)),
                model="whisper-large-v3",
                language="he"
            )
            user_text = transcription.text

        response = await ask_ai(chat_id, user_text)
        await send_split_message(update, response, show_keyboard=True)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("שלח PDF ונתחיל.")))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE, handle_input))
    app.run_polling()
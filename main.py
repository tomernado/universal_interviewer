import os
from groq import Groq
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from tools.pdf_handler import extract_text_from_pdf

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
user_sessions = {}

def get_system_prompt(pdf_text):
    """
    הפונקציה הזו היא ה"דבק". היא פותחת את כל קבצי הקינפוג שלנו
    ומרכיבה מהם את ההוראות השלמות עבור ה-LLM.
    """
    with open('agent_config/soul.md', 'r', encoding='utf-8') as f:
        soul = f.read()
    with open('agent_config/skills.md', 'r', encoding='utf-8') as f:
        skills = f.read()
    with open('agent_config/memory_rules.md', 'r', encoding='utf-8') as f:
        memory = f.read()
        
    return f"{soul}\n\n{skills}\n\n{memory}\n\n--- \nCONTEXT FROM PDF:\n{pdf_text}"

def get_interview_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("רמז 💡", callback_data='hint'), InlineKeyboardButton("דלג שאלה ⏭️", callback_data='skip')],
        [InlineKeyboardButton("סיום סשן 📊", callback_data='summary')]
    ])

async def ask_ai(chat_id, user_input):
    session = user_sessions[chat_id]
    session['history'].append({"role": "user", "content": user_input})
    
    recent_history = session['history'][-6:]
    
    system_prompt = get_system_prompt(session['pdf_text'])
    
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant", 
        messages=[{"role": "system", "content": system_prompt}] + recent_history,
        temperature=0.6,
        max_tokens=800
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
    await update.message.reply_text("טוען את המוח ואת חומר הלימוד... 🧠📚")
    try:
        file = await context.bot.get_file(update.message.document.file_id)
        pdf_bytes = await file.download_as_bytearray()
        
        # שימוש בכלי שיצרנו בתיקייה הנפרדת
        text = extract_text_from_pdf(pdf_bytes)
        
        user_sessions[chat_id] = {'history': [], 'pdf_text': text}
        response = await ask_ai(chat_id, "זהו חומר הרקע. קבל את פני המשתמש בקצרה, ציין 2-3 טכנולוגיות מרכזיות שזיהית במסמך שעליהן תבחן אותו. שים קו מפריד (---) ושאל את השאלה הטכנית הראשונה.")      
        await send_split_message(update, response, show_keyboard=True)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if chat_id not in user_sessions: return

    # שימו לב: אנחנו מעבירים את המילים 'רמז' או 'דלג' ישר ל-LLM,
    # כי לימדנו אותו בקובץ memory_rules.md איך להגיב אליהן!
    if query.data == 'hint':
        response = await ask_ai(chat_id, "רמז")
        await query.message.reply_text(f"💡 {response.strip()}", parse_mode='Markdown')
    elif query.data == 'skip':
        response = await ask_ai(chat_id, "דלג")
        await send_split_message(update, response, show_keyboard=True)
    elif query.data == 'summary':
        response = await ask_ai(chat_id, "סכם את הסשן ואת רמת הידע שלי. אל תשאל שאלה חדשה.")
        await query.message.reply_text(response, parse_mode='Markdown')
        del user_sessions[chat_id]

async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_sessions:
        await update.message.reply_text("שלום! שלח PDF כדי להתחיל.")
        return

    await context.bot.send_chat_action(chat_id=chat_id, action='typing')
    try:
        response = await ask_ai(chat_id, update.message.text)
        await send_split_message(update, response, show_keyboard=True)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_TOKEN")).build()
    app.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("שלח PDF ונתחיל.")))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    app.run_polling()
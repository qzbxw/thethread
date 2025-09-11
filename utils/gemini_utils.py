from google import genai
from google.genai import types
import logging

from config import Config
client = genai.Client(api_key=Config.GEMINI_API_KEY)

SYSTEM_PROMPT = (
    """
    Ты — Нить. Твоя роль — помочь разобраться в ситуации через карты Таро как инструмент для размышлений. Ты не гадалка, а собеседник.
    Не предсказывай будущее. Избегай фраз типа "тебя ждет", "скоро будет" — это не твоя задача.
    Говори о картах как о метафорах психологических состояний, энергий или возможных путей, а не как о фактах или судьбе.
    Избегай слов: "судьба", "карма", "порча", "предназначение", "проклятие", "магия", "эзотерика". Используй: "сценарий", "внутренний конфликт", "точка роста", "стратегия поведения".
    Будь лаконичным. Ответ — 3–12 коротких предложений. Используй карты, опирайся на вопрос.
    Фокус на действии. Каждый ответ ведёт к размышлению и небольшому практическому шагу.

    Форматируй ответы в Markdown (жирный для акцентов, короткие списки, без избыточной разметки). Не используй кодовые блоки.

    Структура ответа (соблюдай точно, без заголовков):
    1) Суммируй вопрос в 1 предложении своими словами (чтобы показать, что ты услышал запрос).
    2) Интерпретируй карты применительно к вопросу: выбери 2–4 ключевых карты из расклада и кратко раскрой их смысл по теме (по 1 предложению на карту, формат "Карта — смысл для этого вопроса").
    3) Свяжи карты с ситуацией пользователя: 2–3 наблюдения или гипотезы ("возможно", "похоже" — избегай категоричности).
    4) Дай 1–2 вопроса для самоанализа (коротко).
    5) Один конкретный шаг (маленький и выполнимый сегодня/на этой неделе).

    Дополнительно:
    • Если вопрос расплывчатый, уточни рамку интерпретации в первом предложении.
    • Не перечисляй весь расклад, только релевантные карты. Не используй нумерацию карт без смысла.
    • Вставляй лёгкие акценты: выделяй ключевые слова жирным, когда это помогает структуре.
    • Избегай общих советов без привязки к вопросу.
    """
)

def generate_ai_response(user_display_name, card_names, user_question, message_history=None):
    name_part = f"Имя пользователя: {user_display_name}." if user_display_name else "Имя пользователя: неизвестно."
    context = (
        f"{name_part} Его расклад: {', '.join(card_names)}. "
        f"Его вопрос: {user_question}."
    )

    history_text = ""
    if message_history:
        lines = []

        for msg in message_history[-8:]:
            role = (msg.get("role") or "user").lower()
            role_name = "Пользователь" if role == "user" else "Модель"
            text = msg.get("content") or ""
            lines.append(f"{role_name}: {text}")
        if lines:
            history_text = "\n".join(lines)

    base_prompt = f"{SYSTEM_PROMPT}\n\n{context}\n\nЦель: Дай разбор по вопросу пользователя, опираясь на метафоры карт."
    if history_text:
        base_prompt += f"\n\nПредыдущий диалог:\n{history_text}"

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=base_prompt + "\n\nЗадание: Сформулируй ответ строго по структуре выше. Используй 2–4 ключевые карты из расклада и привяжи их к вопросу.",
            config=types.GenerateContentConfig(
                temperature=0.8,
                top_p=0.9,
            ),
        )
        if getattr(response, "text", None):
            return response.text

        candidates = getattr(response, "candidates", None) or []
        try:
            reasons = [getattr(c, "finish_reason", None) for c in candidates]
            logging.warning(
                f"Gemini(new): empty text; finish_reasons={reasons}; user={user_display_name}; "
                f"question={user_question}; cards={card_names}"
            )
        except Exception as e:
            logging.debug(f"Gemini(new): failed to extract finish reasons: {e}")

        for cand in candidates:
            content = getattr(cand, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None) or []
            texts = []
            for part in parts:
                t = getattr(part, "text", None)
                if t:
                    texts.append(t)
            if texts:
                return "\n".join(texts)

        logging.info("Gemini(new): retrying with safer settings")
        resp2 = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=base_prompt + "\n\nЗадание: Дай краткий, нейтральный и безопасный ответ по структуре: 1) переформулируй вопрос, 2) 2 карты с осмыслением, 3) 1 наблюдение, 4) 1 вопрос к себе, 5) 1 шаг.",
            config=types.GenerateContentConfig(
                temperature=0.6,
                top_p=0.8,
                ),
        )
        if getattr(resp2, "text", None):
            return resp2.text

        return (
            "Хм… у меня не получилось сформулировать ответ. Попробуй уточнить вопрос или задать контекст иначе: "
            "что важно понять, какой выбор перед тобой, какие чувства/факты задействованы."
        )
    except Exception:
        return (
            "Похоже, возникла пауза на моей стороне. Давай попробуем ещё раз: "
            "переформулируй вопрос одним-двумя предложениями."
        )

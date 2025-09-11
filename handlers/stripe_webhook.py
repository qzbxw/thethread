import aiohttp
import json
import stripe
from aiohttp import web
from datetime import datetime, timedelta
import logging

from models.database import db
from utils.logging_utils import log_payment, main_bot
from utils.ui import main_menu_kb
from config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY

async def handle_webhook(request):
    payload = await request.read()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, Config.STRIPE_WEBHOOK_SECRET)
    except ValueError:
        logging.warning("Stripe webhook: invalid payload")
        return web.Response(status=400)
    except stripe.error.SignatureVerificationError:
        logging.warning("Stripe webhook: signature verification failed")
        return web.Response(status=400)
    
    logging.info(f"Stripe webhook: received event {event.get('type')}")
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        user_id = int(session['metadata']['user_id'])
        chat_id = int(session['metadata'].get('chat_id', user_id))
        crystals = int(session['metadata']['crystals'])
        amount_usd = session['amount_total'] / 100 
        
        payment_id = session['payment_intent']
        if await db.transaction_exists(payment_id):
            logging.info(f"Stripe webhook: transaction {payment_id} already recorded, skipping")
            return web.Response(status=200)

        await db.update_balance(user_id, crystals)
        

        await db.record_transaction(user_id, payment_id, amount_usd, crystals)
        
        user = await db.get_user(user_id)
        await log_payment(user['username'] or str(user_id), crystals, amount_usd)

        try:
            if main_bot:
                user = await db.get_user(user_id)
                balance_now = user['balance_crystals'] if user else 0
                free_available = True
                if user and user['last_free_card_ts']:
                    try:
                        delta = datetime.now() - user['last_free_card_ts']
                        free_available = delta >= timedelta(hours=Config.FREE_CARD_COOLDOWN_HOURS)
                    except Exception:
                        free_available = True
                text = (
                    "Платёж подтверждён ✅\n"
                    f"На баланс зачислено: <b>{crystals}</b> 💎\n\n"
                    f"Баланс: <b>{balance_now}</b> 💎"
                )
                await main_bot.send_message(chat_id, text)
                mid = session['metadata'].get('message_id') if session.get('metadata') else None
                if mid:
                    try:
                        await main_bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=int(mid),
                            text=(
                                "Платёж подтверждён ✅\n"
                                f"Баланс обновлён: <b>{balance_now}</b> 💎\n\n"
                                "Выбирай, что дальше:"
                            ),
                            reply_markup=main_menu_kb(balance=balance_now, free_available=free_available),
                        )
                    except Exception as e:
                        logging.warning(f"Edit original message failed: {e}")
                        try:
                            await main_bot.send_message(
                                chat_id,
                                "Готово! Баланс пополнен.\nОткрою меню:",
                                reply_markup=main_menu_kb(balance=balance_now, free_available=free_available),
                            )
                        except Exception as e2:
                            logging.error(f"Failed to notify user {chat_id} about payment via send_message: {e2}")
        except Exception as e:
            logging.exception(f"Unexpected error while notifying user {chat_id} about payment confirmation: {e}")
    
    return web.Response(status=200)

async def start_webhook_server():
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    def _success_html(credited: bool, crystals: int | None = None) -> str:
        cta_href = f"https://t.me/{Config.BOT_USERNAME}" if Config.BOT_USERNAME else "tg://resolve"
        status = "Оплата подтверждена" if credited else "Оплата успешно завершена"
        sub = (
            f"На баланс зачислено: <b>{crystals}</b> 💎. Можно вернуться в бота." if credited
            else "Если баланс не обновился автоматически, вернись в бота — он проверит и обновит в течение минуты."
        )
        return f"""
        <!doctype html>
        <html lang=\"ru\">
        <head>
            <meta charset=\"utf-8\" />
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
            <title>Оплата — Нить</title>
            <style>
                :root {{ --bg:#0d1117; --card:#161b22; --text:#c9d1d9; --accent:#7ee787; --muted:#8b949e; --btn:#238636; --btnh:#2ea043; }}
                body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
                .card {{ background:var(--card); padding:28px 22px; border-radius:16px; max-width:520px; width:92%; box-shadow:0 10px 30px rgba(0,0,0,.35); border:1px solid #30363d; }}
                h1 {{ margin:0 0 8px; font-size:22px; }}
                p {{ margin:6px 0 0; color:var(--muted); }}
                .ok {{ color:var(--accent); font-weight:600; }}
                .cta {{ margin-top:18px; display:flex; gap:10px; flex-wrap:wrap; }}
                a.btn {{ background:var(--btn); color:#fff; text-decoration:none; padding:10px 14px; border-radius:10px; font-weight:600; display:inline-flex; align-items:center; gap:8px; }}
                a.btn:hover {{ background:var(--btnh); }}
                .note {{ margin-top:12px; font-size:13px; color:var(--muted); }}
            </style>
        </head>
        <body>
            <main class=\"card\">
                <h1 class=\"ok\">✅ {status}</h1>
                <p>{sub}</p>
                <div class=\"cta\">
                    <a class=\"btn\" href=\"{cta_href}\">Вернуться в Telegram</a>
                </div>
                <div class=\"note\">Если окно Stripe всё ещё открыто — можешь закрыть эту вкладку.</div>
            </main>
        </body>
        </html>
        """

    def _cancel_html() -> str:
        cta_href = f"https://t.me/{Config.BOT_USERNAME}" if Config.BOT_USERNAME else "tg://resolve"
        return f"""
        <!doctype html>
        <html lang=\"ru\">
        <head>
            <meta charset=\"utf-8\" />
            <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
            <title>Оплата отменена — Нить</title>
            <style>
                :root {{ --bg:#0d1117; --card:#161b22; --text:#c9d1d9; --muted:#8b949e; --btn:#30363d; --btnh:#484f58; }}
                body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.5 system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Helvetica, Arial; display:flex; min-height:100vh; align-items:center; justify-content:center; }}
                .card {{ background:var(--card); padding:28px 22px; border-radius:16px; max-width:520px; width:92%; box-shadow:0 10px 30px rgba(0,0,0,.35); border:1px solid #30363d; }}
                h1 {{ margin:0 0 8px; font-size:22px; }}
                p {{ margin:6px 0 0; color:var(--muted); }}
                .cta {{ margin-top:18px; display:flex; gap:10px; flex-wrap:wrap; }}
                a.btn {{ background:var(--btn); color:#fff; text-decoration:none; padding:10px 14px; border-radius:10px; font-weight:600; display:inline-flex; align-items:center; gap:8px; }}
                a.btn:hover {{ background:var(--btnh); }}
            </style>
        </head>
        <body>
            <main class=\"card\">
                <h1>Оплата отменена</h1>
                <p>Ты можешь вернуться и выбрать другой пакет или попробовать снова.</p>
                <div class=\"cta\"><a class=\"btn\" href=\"{cta_href}\">Вернуться в Telegram</a></div>
            </main>
        </body>
        </html>
        """

    async def handle_success(request):
        session_id = request.query.get('session_id')
        credited = False
        crystals = None
        if session_id:
            try:
                session = stripe.checkout.Session.retrieve(session_id)
                payment_intent = session.get('payment_intent')
                if session.get('payment_status') == 'paid' and payment_intent:
                    user_id = int(session['metadata']['user_id'])
                    chat_id = int(session['metadata'].get('chat_id', user_id))
                    crystals = int(session['metadata']['crystals'])
                    amount_usd = session.get('amount_total', 0) / 100
                    if not await db.transaction_exists(payment_intent):
                        await db.update_balance(user_id, crystals)
                        await db.record_transaction(user_id, payment_intent, amount_usd, crystals)
                        try:
                            if main_bot:
                                await main_bot.send_message(
                                    chat_id,
                                    f"Платёж подтверждён ✅\nНа баланс зачислено: <b>{crystals}</b> 💎",
                                )
                        except Exception as e:
                            logging.warning(f"Failed to send success message to user {chat_id} in /success handler: {e}")
                    return web.Response(text="Оплата подтверждена. Кристаллы начислены.")
            except Exception as e:
                logging.exception("/success verification failed")
        return web.Response(text="Оплата прошла успешно. Можешь вернуться в бот — кристаллы будут начислены после подтверждения.")
    async def handle_cancel(request):
        return web.Response(text="Оплата отменена. Ты можешь вернуться и выбрать другой пакет или попробовать снова.")
    app.router.add_get('/success', handle_success)
    app.router.add_get('/cancel', handle_cancel)
    async def handle_favicon(request):
        svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><text y='14' x='0' font-size='14'>✨</text></svg>"""
        return web.Response(text=svg, content_type='image/svg+xml')
    app.router.add_get('/favicon.ico', handle_favicon)
    async def handle_health(request):
        return web.Response(text="ok")
    app.router.add_get('/healthz', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    import os
    port = int(os.getenv('PORT', '8000'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Webhook server started on http://0.0.0.0:{port} (use PUBLIC_BASE_URL for external access)")

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_webhook_server())

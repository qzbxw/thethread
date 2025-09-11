import stripe
import logging

from config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY

def create_checkout_session(user_id, package, chat_id, message_id: int | None = None):
    packages = {
        "probe": {"crystals": Config.CRYSTALS_PROBE, "price": Config.PRICE_PROBE_CENTS},
        "standard": {"crystals": Config.CRYSTALS_STANDARD, "price": Config.PRICE_STANDARD_CENTS},
        "premium": {"crystals": Config.CRYSTALS_PREMIUM, "price": Config.PRICE_PREMIUM_CENTS},
    }
    
    if package not in packages:
        raise ValueError("Invalid package")

    base_url = Config.PUBLIC_BASE_URL.strip() or "http://localhost:8000"
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'{packages[package]["crystals"]} Кристаллов',
                    },
                    'unit_amount': packages[package]["price"],
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{base_url}/cancel',
            metadata={
                'user_id': str(user_id),
                'chat_id': str(chat_id),
                'message_id': str(message_id) if message_id is not None else '',
                'crystals': str(packages[package]["crystals"]),
            }
        )
    except Exception as e:
        logging.exception(f"Stripe checkout create failed (base_url={base_url}): {e}")
        raise
    
    return session.url, packages[package]["crystals"], session.id

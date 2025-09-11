from aiogram import Dispatcher

from .start import register_start_handler
from .balance import register_balance_handler
from .buy_crystals import register_buy_crystals_handler
from .tarot import register_tarot_handler
from .policies import register_policies_handler
from .cancel import register_cancel_handler

def register_handlers(dp: Dispatcher):
    register_start_handler(dp)
    register_balance_handler(dp)
    register_buy_crystals_handler(dp)
    register_tarot_handler(dp)
    register_policies_handler(dp)
    register_cancel_handler(dp)
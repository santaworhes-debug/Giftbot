from handlers.user_handlers import user_router
from handlers.admin_handlers import admin_router
from handlers.games_handlers import games_router
from handlers.inline_handlers import inline_router

__all__ = ["user_router", "admin_router", "games_router", "inline_router"]

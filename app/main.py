import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot
from aiogram.types import BotCommand
from fastapi import FastAPI

sys.path.append(str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.expenses.router import router as router_expenses
from app.llm.classifier import ExpenseCategoryClassifier
from app.llm.gigachat import build_gigachat_provider
from app.llm.queue import ClassificationQueue


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    provider = build_gigachat_provider(settings)
    app.state.gigachat_provider = provider

    classifier = ExpenseCategoryClassifier(provider)
    queue = ClassificationQueue(classifier)
    await queue.start()
    app.state.classification_queue = queue

    bot = Bot(token=settings.BOT_TOKEN)
    session_factory = get_session_factory()

    await bot.set_my_commands([
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="list", description="Мои расходы"),
    ])

    from app.bot.handlers import dp
    polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            session_factory=session_factory,
            classification_queue=queue,
        )
    )

    yield

    polling_task.cancel()
    await asyncio.gather(polling_task, return_exceptions=True)
    await bot.session.close()
    await queue.stop()
    await provider.aclose()


app = FastAPI(lifespan=lifespan)

app.include_router(router_expenses)

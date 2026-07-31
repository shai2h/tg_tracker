from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService
from app.llm.classifier import ExpenseCategoryClassifier
from app.llm.gigachat import GigaChatProvider


def get_expense_repository(
    session: AsyncSession = Depends(get_db),
) -> ExpenseRepository:
    return ExpenseRepository(session)


def get_gigachat_provider() -> GigaChatProvider:
    settings = get_settings()
    return GigaChatProvider(
        api_key=settings.GIGACHAT_AUTH_KEY,
        scope=settings.GIGACHAT_SCOPE,
        oauth_url=settings.GIGACHAT_OAUTH_URL,
        api_base_url=settings.GIGACHAT_API_BASE_URL,
        model=settings.GIGACHAT_MODEL,
        verify_ssl=settings.GIGACHAT_VERIFY_SSL,
        timeout_seconds=settings.GIGACHAT_TIMEOUT_SECONDS,
        max_tokens=settings.GIGACHAT_MAX_TOKENS,
        temperature=settings.GIGACHAT_TEMPERATURE,
    )


def get_expense_category_classifier(
    provider: GigaChatProvider = Depends(get_gigachat_provider),
) -> ExpenseCategoryClassifier:
    return ExpenseCategoryClassifier(provider)


def get_expense_service(
    repository: ExpenseRepository = Depends(get_expense_repository),
    classifier: ExpenseCategoryClassifier = Depends(get_expense_category_classifier),
) -> ExpenseService:
    return ExpenseService(repository, classifier)

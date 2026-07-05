from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db, get_session_factory
from app.expenses.repository import ExpenseRepository
from app.expenses.service import ExpenseService
from app.llm.classifier import ExpenseCategoryClassifier
from app.llm.gigachat import GigaChatProvider
from app.llm.queue import ClassificationQueue


def get_expense_repository(
    session: AsyncSession = Depends(get_db),
) -> ExpenseRepository:
    return ExpenseRepository(session)


def get_gigachat_provider(request: Request) -> GigaChatProvider:
    return request.app.state.gigachat_provider


def get_expense_category_classifier(
    provider: GigaChatProvider = Depends(get_gigachat_provider),
) -> ExpenseCategoryClassifier:
    return ExpenseCategoryClassifier(provider)


def get_classification_queue(request: Request) -> ClassificationQueue:
    return request.app.state.classification_queue


def get_expense_service(
    repository: ExpenseRepository = Depends(get_expense_repository),
    queue: ClassificationQueue = Depends(get_classification_queue),
) -> ExpenseService:
    return ExpenseService(repository, queue, get_session_factory())

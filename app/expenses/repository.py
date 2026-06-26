from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.expenses.models import ExpenseOrm, UserOrm


class ExpenseRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: UUID, title: str, amount_kopeiki: int):
        expense = ExpenseOrm(
            user_id=user_id,
            title=title,
            amount_kopeiki=amount_kopeiki,
        )

        self.session.add(expense)
        await self.session.flush()
        await self.session.refresh(expense)

        return expense

    async def get_by_user_id(
        self,
        user_id: UUID,
        limit: int,
        offset: int,
    ):
        stmt = (
            select(ExpenseOrm)
            .where(ExpenseOrm.user_id == user_id)
            .order_by(ExpenseOrm.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_id(self, expense_id: UUID):
        stmt = select(ExpenseOrm).where(ExpenseOrm.id == expense_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        expense_id: UUID,
        title: str,
        amount_kopeiki: int,
    ):
        stmt = (
            update(ExpenseOrm)
            .where(ExpenseOrm.id == expense_id)
            .values(
                title=title,
                amount_kopeiki=amount_kopeiki,
            )
            .returning(ExpenseOrm)
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def delete(self, expense_id: UUID):
        stmt = (
            delete(ExpenseOrm)
            .where(ExpenseOrm.id == expense_id)
            .returning(ExpenseOrm.id)
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_id: int):
        stmt = select(UserOrm).where(UserOrm.telegram_id == telegram_id)

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def create_user(
        self,
        telegram_id: int,
        username: str | None,
    ):
        try:
            user = UserOrm(
                telegram_id=telegram_id,
                username=username,
            )

            self.session.add(user)
            await self.session.flush()
            await self.session.refresh(user)

            return user
        except IntegrityError:
            user = await self.get_user_by_telegram_id(telegram_id)
            return user

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None,
    ):
        user = await self.get_user_by_telegram_id(telegram_id)

        if user is not None:
            if username and user.username != username:
                user.username = username
                await self.session.flush()
                await self.session.refresh(user)
            return user

        return await self.create_user(
            telegram_id=telegram_id,
            username=username,
        )

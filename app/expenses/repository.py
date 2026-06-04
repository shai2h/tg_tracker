from sqlalchemy.orm import Session

from app.expenses.models import Expense


class ExpenseRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        title: str,
        amount: int,
    ) -> Expense:
        expense = Expense(
            user_id=user_id,
            title=title,
            amount=amount,
        )

        self.db.add(expense)
        self.db.commit()
        self.db.refresh(expense)

        return expense

    def get_by_user_id(self, user_id: int) -> list[Expense]:
        return (
            self.db.query(Expense)
            .filter(Expense.user_id == user_id)
            .order_by(Expense.created_at.desc())
            .all()
        )

    def delete_by_id_and_user_id(
        self,
        expense_id: int,
        user_id: int,
    ) -> bool:
        expense = (
            self.db.query(Expense)
            .filter(
                Expense.id == expense_id,
                Expense.user_id == user_id,
            )
            .first()
        )

        if expense is None:
            return False

        self.db.delete(expense)
        self.db.commit()

        return True
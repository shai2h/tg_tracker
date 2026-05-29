from sqlalchemy.orm import Session

from app.models import Expense


def create_expense(
    db: Session,
    user_id: int,
    title: str,
    amount: int,
) -> Expense:
    expense = Expense(
        user_id=user_id,
        title=title,
        amount=amount,
    )

    db.add(expense)
    db.commit()
    db.refresh(expense)

    return expense


def get_user_expenses(db: Session, user_id: int) -> list[Expense]:
    return (
        db.query(Expense)
        .filter(Expense.user_id == user_id)
        .order_by(Expense.created_at.desc())
        .all()
    )


def delete_expense(db: Session, expense_id: int, user_id: int) -> bool:
    expense = (
        db.query(Expense)
        .filter(
            Expense.id == expense_id,
            Expense.user_id == user_id,
        )
        .first()
    )

    if expense is None:
        return False

    db.delete(expense)
    db.commit()

    return True
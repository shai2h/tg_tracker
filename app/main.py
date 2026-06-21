from fastapi import FastAPI
import uvicorn

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.expenses.router import router as router_expenses
from app.expenses.bot_router import router as bot_expenses_router


app = FastAPI()

app.include_router(router_expenses)
app.include_router(bot_expenses_router)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

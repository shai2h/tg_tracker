from fastapi import FastAPI
import uvicorn

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.expenses.router import router as router_expenses


app = FastAPI()

app.include_router(router_expenses)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

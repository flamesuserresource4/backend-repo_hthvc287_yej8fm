import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, conint, confloat

app = FastAPI(title="Fast Loan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoanInput(BaseModel):
    principal: confloat(gt=0) = Field(..., description="Loan amount")
    annual_rate: confloat(ge=0) = Field(..., description="Annual interest rate in %")
    term_months: conint(gt=0) = Field(..., description="Loan term in months")
    extra_payment: confloat(ge=0) = Field(0, description="Optional extra monthly payment applied to principal")


class ScheduleItem(BaseModel):
    month: int
    payment: float
    interest: float
    principal: float
    balance: float


class LoanResult(BaseModel):
    monthly_payment: float
    total_payment: float
    total_interest: float
    payoff_months: int
    apr: float
    schedule: Optional[List[ScheduleItem]] = None


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.post("/api/calculate-loan", response_model=LoanResult)
def calculate_loan(payload: LoanInput):
    P = float(payload.principal)
    r = float(payload.annual_rate) / 100.0 / 12.0  # monthly rate
    n = int(payload.term_months)
    extra = float(payload.extra_payment or 0)

    if P <= 0 or n <= 0 or payload.annual_rate < 0:
        raise HTTPException(status_code=400, detail="Invalid inputs")

    # Handle zero interest gracefully
    if r == 0:
        base_payment = P / n
    else:
        base_payment = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)

    payment = base_payment + extra

    balance = P
    schedule: List[ScheduleItem] = []
    total_interest = 0.0
    month = 0

    # Amortization loop with safety cap
    safety_cap = n + 600  # allow extra months if extra_payment is 0 and rounding
    while balance > 0.005 and month < safety_cap:
        month += 1
        interest_component = balance * r
        principal_component = payment - interest_component

        # If interest exceeds payment (very low payment), avoid negative amortization
        if principal_component <= 0 and r > 0:
            raise HTTPException(status_code=400, detail="Payment too low to cover interest. Increase term or rate settings.")

        if principal_component > balance:
            principal_component = balance
            payment_actual = interest_component + principal_component
        else:
            payment_actual = payment

        balance = balance - principal_component
        total_interest += interest_component

        schedule.append(
            ScheduleItem(
                month=month,
                payment=round(payment_actual, 2),
                interest=round(interest_component, 2),
                principal=round(principal_component, 2),
                balance=round(max(balance, 0.0), 2),
            )
        )

        if month > 3600:  # absolute fail-safe
            break

    total_payment = sum(item.payment for item in schedule)

    result = LoanResult(
        monthly_payment=round(payment, 2),
        total_payment=round(total_payment, 2),
        total_interest=round(total_interest, 2),
        payoff_months=len(schedule),
        apr=round(float(payload.annual_rate), 3),
        schedule=schedule,
    )
    return result


@app.get("/test")
def test_database():
    """Test endpoint to check base backend & env setup."""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Used (no persistence for calculator)",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "No DB required for this app",
        "collections": [],
    }

    # Check environment variables (for completeness)
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

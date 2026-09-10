from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/customers",
    tags=["Customers"]
)

@router.post(
    "",
    response_model=schemas.CustomerResponse,
    status_code=201
)

def create_customer(
        customer: schemas.CustomerCreate,
        db: Session = Depends(get_db)
):
    new_customer = models.Customer(
        name=customer.name,
        phone_number=customer.phone_number,
        email=customer.email
    )

    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)

    return new_customer


@router.get(
    "",
    response_model=list[schemas.CustomerResponse],
)
def get_customers(
        db: Session = Depends(get_db)
):
    return db.query(models.Customer).all()


@router.get(
    "/{customer_id}",
    response_model=schemas.CustomerResponse
)
def get_customer(
        customer_id: int,
        db: Session = Depends(get_db)
):
    customer = (
        db.query(models.Customer).filter(models.Customer.id == customer_id)
        .first()
    )

    if customer is None:
        raise HTTPException(
            status_code=404,
            detail="Customer not found"
        )

    return customer
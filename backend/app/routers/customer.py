"""Customer area. Every query is filtered by the signed-in customer's id, so one
customer can never read or change another's booking; unknown references are 404."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import booking_service
from ..database import get_db
from ..errors import ApiError
from ..models import Account, Booking
from ..rate_limit import limiter
from ..schemas import BookingCreate, BookingReceipt, CancellationRequestIn, CustomerBookingList, CustomerBookingOut
from ..security import require_customer

router = APIRouter(prefix="/api/customer", tags=["customer"])


@router.post("/bookings", response_model=BookingReceipt, status_code=201)
def create_booking(data: BookingCreate, response: Response, customer: Account = Depends(require_customer),
                   db: Session = Depends(get_db)):
    """A request linked to the signed-in customer. The link comes from the
    session; the body has no customer, status, reference or staff fields."""
    limiter.hit(f"booking:customer:{customer.id}", limit=10, window_seconds=10 * 60)
    booking, created = booking_service.create_booking(db, data, customer)
    if not created:
        response.status_code = 200
    return BookingReceipt(reference=booking.reference, status="pending", message=booking_service.RECEIVED_MESSAGE)


@router.get("/bookings", response_model=CustomerBookingList)
def list_bookings(
    response: Response,
    when: Literal["upcoming", "past"] | None = None,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    customer: Account = Depends(require_customer),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    conditions = [Booking.customer_id == customer.id]
    today = booking_service.now_local().date()
    active = Booking.status.in_(("pending", "confirmed", "checked_in"))
    if when == "upcoming":
        conditions += [Booking.requested_date >= today, active]
        order = (Booking.requested_at, Booking.id)
    elif when == "past":
        conditions.append((Booking.requested_date < today) | ~active)
        order = (Booking.requested_at.desc(), Booking.id.desc())
    else:
        order = (Booking.requested_at.desc(), Booking.id.desc())
    total = db.scalar(select(func.count()).select_from(Booking).where(*conditions))
    rows = db.scalars(select(Booking).where(*conditions).order_by(*order).limit(limit).offset(offset)).all()
    return CustomerBookingList(items=[booking_service.customer_view(b) for b in rows], total=total, limit=limit, offset=offset)


@router.get("/bookings/{reference}", response_model=CustomerBookingOut)
def get_booking(reference: str, response: Response, customer: Account = Depends(require_customer),
                db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "no-store"
    booking = db.scalar(select(Booking).where(Booking.reference == reference, Booking.customer_id == customer.id))
    if booking is None:
        raise ApiError(404, "not_found", "We couldn't find that booking.")
    return booking_service.customer_view(booking)


@router.post("/bookings/{reference}/cancellation-request", response_model=CustomerBookingOut)
def request_cancellation(reference: str, data: CancellationRequestIn, customer: Account = Depends(require_customer),
                         db: Session = Depends(get_db)):
    """Asks staff to cancel. The booking keeps its status until staff decide."""
    limiter.hit(f"cancel-request:customer:{customer.id}", limit=10, window_seconds=60 * 60)
    return booking_service.customer_view(booking_service.request_cancellation(db, reference, customer, data.reason))

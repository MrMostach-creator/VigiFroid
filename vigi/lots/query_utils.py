# vigi/lots/query_utils.py
from datetime import date, timedelta
from sqlalchemy import or_, and_
from models import Lot

def build_lot_query(q: str = "", status: str = ""):
    query = Lot.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Lot.product_name.ilike(like),
            Lot.lot_number.ilike(like),
            Lot.pn.ilike(like),
        ))
    today = date.today()
    if status == "valid":
        query = query.filter(Lot.expiry_date > today + timedelta(days=30))
    elif status == "warning":
        query = query.filter(and_(Lot.expiry_date >= today,
                                  Lot.expiry_date <= today + timedelta(days=30)))
    elif status == "expired":
        query = query.filter(Lot.expiry_date < today)
    return query.order_by(Lot.expiry_date.asc())

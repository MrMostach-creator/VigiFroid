# test_app.py


import pytest # pyright: ignore[reportMissingImports]
from app import app # pyright: ignore[reportMissingImports]

@pytest.fixture
def client():
    with app.test_client() as client: # pyright: ignore[reportUndefinedVariable]
        yield client

def test_login(client):
    response = client.post('/login', data=dict(username='admin', password='admin'), follow_redirects=True)
    assert response.status_code == 200
    assert b'VigiFroid' in response.data

def test_add_lot(client):
    with client.session_transaction() as session:
        session['user_id'] = 1  # Simulate logged-in admin
    response = client.post('/', data=dict(lot_number='123', expiry_date='2025-12-31', product_name='Loctite'), follow_redirects=True)
    assert response.status_code == 200
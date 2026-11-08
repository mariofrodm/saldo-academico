from datetime import date
from decimal import Decimal

from backend.db import db, one, many


def test_edit_start_month_and_configuration_preserve_existing_snapshots(client, auth):
    created = client.post('/api/v1/recurring', headers=auth, json={
        'category_id': 2, 'title': 'Internet', 'amount': '220.00', 'start_month': '2026-11-15'})
    assert created.status_code == 200 and created.json()['start_month'] == '2026-11-01'
    ident = created.json()['id']
    client.get('/api/v1/board?month=2026-11-01', headers=auth)
    with db() as conn:
        previous = one(conn, 'SELECT * FROM obligations WHERE recurring_id=%s', (ident,))
    assert previous['planned'] == Decimal('220.00')
    changed = client.put(f'/api/v1/recurring/{ident}', headers=auth, json={
        'category_id': 3, 'title': 'Mensualidad actualizada', 'amount': '300.00',
        'start_month': '2027-01-20', 'active': True})
    assert changed.status_code == 200 and changed.json()['start_month'] == '2027-01-01'
    client.get('/api/v1/board?month=2026-12-01', headers=auth)
    with db() as conn:
        assert many(conn, 'SELECT * FROM obligations WHERE recurring_id=%s', (ident,)) == [previous]
    client.get('/api/v1/board?month=2027-01-01', headers=auth)
    with db() as conn:
        rows = many(conn, 'SELECT * FROM obligations WHERE recurring_id=%s ORDER BY due_date', (ident,))
        assert rows[0] == previous
        assert rows[1]['planned'] == Decimal('300.00') and rows[1]['title'] == 'Mensualidad actualizada'
        assert rows[1]['category_id'] == 3 and rows[1]['due_date'] == date(2027, 1, 1)
        assert one(conn, "SELECT id FROM audit WHERE action='update' AND entity='recurring' AND entity_id=%s", (str(ident),))


def test_edit_start_month_backwards_only_instantiates_missing_months(client, auth):
    payload = {'category_id': 2, 'title': 'Mensualidad', 'amount': '100.00', 'start_month': '2027-02-01'}
    ident = client.post('/api/v1/recurring', headers=auth, json=payload).json()['id']
    client.get('/api/v1/board?month=2027-02-01', headers=auth)
    assert client.put(f'/api/v1/recurring/{ident}', headers=auth, json={**payload, 'amount': '120.00', 'start_month': '2027-01-01'}).status_code == 200
    for month in ('2027-01-01', '2027-02-01', '2027-02-01'):
        client.get('/api/v1/board?month='+month, headers=auth)
    with db() as conn:
        rows = many(conn, 'SELECT due_date,planned FROM obligations WHERE recurring_id=%s ORDER BY due_date', (ident,))
        assert rows == [{'due_date': date(2027, 1, 1), 'planned': Decimal('120.00')},
                        {'due_date': date(2027, 2, 1), 'planned': Decimal('100.00')}]


def test_recurring_edit_ownership_and_invalid_dates_do_not_modify_record(client, auth, admin_auth):
    payload = {'category_id': 2, 'title': 'Privado', 'amount': '100.00', 'start_month': '2027-01-01'}
    ident = client.post('/api/v1/recurring', headers=auth, json=payload).json()['id']
    assert client.put(f'/api/v1/recurring/{ident}', headers=admin_auth, json={**payload, 'start_month': '2027-02-01'}).status_code == 404
    assert client.put(f'/api/v1/recurring/{ident}', headers=auth, json={**payload, 'start_month': '2027-02-30'}).status_code == 422
    with db() as conn:
        assert one(conn, 'SELECT start_month FROM recurring WHERE id=%s', (ident,))['start_month'] == date(2027, 1, 1)

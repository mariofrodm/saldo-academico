"""Escenario académico aditivo para la cuenta de demostración, nunca datos reales.

Se ejecuta de forma explícita: ``python -m backend.demo``. No forma parte del
arranque de la aplicación ni modifica cuentas, sesiones o consumo de IA.
"""
import json
import os
from datetime import date
from decimal import Decimal

from .db import db, many, one
from .domain import finance_summary


EMAIL = 'demo@example.test'
VERSION = 'demo_seed_v1'
ACCOUNT_MARKER = 'seed_account_v1'
CUTOFF = date(2026, 11, 2)


def _summary(conn, user_id, created, normalized, already_present):
    counts = {}
    for table in ('categories', 'obligations', 'recurring', 'goals'):
        counts[table] = one(conn, f'SELECT count(*) AS n FROM {table} WHERE user_id=%s', (user_id,))['n']
    counts['payments'] = one(conn, '''SELECT count(*) AS n FROM payments p
        JOIN obligations o ON o.id=p.obligation_id WHERE o.user_id=%s''', (user_id,))['n']
    counts['savings'] = one(conn, '''SELECT count(*) AS n FROM savings s
        JOIN goals g ON g.id=s.goal_id WHERE g.user_id=%s''', (user_id,))['n']
    periods = {}
    for month, end in ((9, 30), (10, 31), (11, 2)):
        periods[f'2026-{month:02}'] = finance_summary(conn, user_id, date(2026, month, 1), date(2026, month, end))
    debts = many(conn, '''SELECT o.title,o.planned,coalesce(sum(p.amount),0) AS paid,
        o.planned-coalesce(sum(p.amount),0) AS remaining FROM obligations o
        JOIN categories c ON c.id=o.category_id LEFT JOIN payments p ON p.obligation_id=o.id
        WHERE o.user_id=%s AND c.name='Deudas' AND NOT o.voided
        GROUP BY o.id ORDER BY remaining,o.id''', (user_id,))
    future = one(conn, '''SELECT count(*) AS n FROM payments p JOIN obligations o ON o.id=p.obligation_id
        WHERE o.user_id=%s AND p.paid_on>%s''', (user_id, CUTOFF))['n']
    future += one(conn, '''SELECT count(*) AS n FROM savings s JOIN goals g ON g.id=s.goal_id
        WHERE g.user_id=%s AND s.moved_on>%s''', (user_id, CUTOFF))['n']
    return {'scenario': VERSION, 'user_email': EMAIL, 'cutoff': CUTOFF.isoformat(),
            'already_present': already_present, 'created': created, 'normalized_legacy_dates': normalized,
            'counts': counts, 'financial_periods': periods, 'debts': debts,
            'existing_future_movements': future,
            'notes': ['Todos los importes están expresados en GTQ.',
                      'Noviembre contiene únicamente movimientos realizados hasta el día 2; las partidas sin pago son previsiones.',
                      'Las tres deudas registran compromisos totales y pagos; no incluyen TAE, intereses, cuotas mínimas ni cronograma contractual.',
                      'Las plantillas activas comienzan en diciembre para no duplicar las partidas ya registradas de noviembre.',
                      'Disponible significa flujo del período: ingresos cobrados menos gastos pagados menos ahorro neto, no saldo bancario.']}


def scenario_user(conn, user_id=None):
    """Validate the established local account independently of its visible name."""
    if os.getenv('APP_ENV', 'local') != 'local':
        raise ValueError('La carga inicial solo está permitida con APP_ENV=local.')
    user = one(conn, 'SELECT * FROM users WHERE email=%s FOR UPDATE', (EMAIL,))
    if not user or (user_id is not None and user['id'] != user_id) or user['role'] != 'user':
        raise ValueError('La carga exige la cuenta local inicializada demo@example.test con rol user.')
    marker = one(conn, '''SELECT id FROM audit WHERE actor_id=%s AND action=ANY(%s) AND entity_id=%s LIMIT 1''',
                 (user['id'], [ACCOUNT_MARKER, VERSION], str(user['id'])))
    if not marker and 'datos ficticios' not in user['name'].lower():
        raise ValueError('La carga exige el marcador de la cuenta local inicializada demo@example.test.')
    return user


def populate_demo(conn, user_id=None):
    """Agrega una sola vez el escenario y devuelve un resumen sin credenciales.

    La transacción anidada también revierte todo si falla una inserción cuando
    el llamador captura la excepción y mantiene abierta su propia transacción.
    Un bloqueo de la fila del usuario evita dos cargas concurrentes.
    """
    with conn.transaction():
        user = scenario_user(conn, user_id)
        uid = user['id']
        marker = one(conn, 'SELECT id FROM audit WHERE actor_id=%s AND action=%s AND entity_id=%s',
                     (uid, VERSION, str(uid)))
        if marker:
            return _summary(conn, uid, {}, 0, True)

        created = {name: 0 for name in ('categories', 'obligations', 'payments', 'recurring', 'goals', 'savings')}
        # La semilla original situaba en el futuro cuatro movimientos conocidos.
        # Solo se corrigen esas coincidencias exactas, conservando IDs e importes.
        normalized = 0
        legacy = [('Sueldo de noviembre ficticio', 'Sueldo', '6000.00', '6000.00'),
                  ('Sueldo de noviembre', 'Sueldo', '6000.00', '6000.00'),
                  ('Alimentación noviembre', 'Alimentación', '1000.00', '1000.00'),
                  ('Universidad noviembre', 'Universidad', '900.00', '400.00')]
        for title, category, planned, paid in legacy:
            result = conn.execute('''UPDATE payments p SET paid_on='2026-11-01'
                FROM obligations o JOIN categories c ON c.id=o.category_id
                WHERE p.obligation_id=o.id AND o.user_id=%s AND o.title=%s AND c.name=%s
                AND o.planned=%s AND p.amount=%s AND p.paid_on='2026-11-05'
                AND p.id=(SELECT min(original.id) FROM payments original WHERE original.obligation_id=o.id)''',
                (uid, title, category, planned, paid))
            normalized += result.rowcount
        normalized += conn.execute('''UPDATE savings s SET moved_on='2026-11-01'
            FROM goals g WHERE s.goal_id=g.id AND g.user_id=%s AND g.name='Fondo de emergencia'
            AND g.target=5000 AND s.amount=500 AND s.moved_on='2026-11-05'
            AND s.id=(SELECT min(original.id) FROM savings original WHERE original.goal_id=g.id)''', (uid,)).rowcount
        if normalized:
            conn.execute('INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)',
                         (uid, 'demo_normalize_dates_v1', 'movimientos_seed', str(normalized)))

        category_ids = {}
        names = [('Sueldo', 'income'), ('Freelance', 'income'), ('Alimentación', 'expense'),
                 ('Universidad', 'expense'), ('Vivienda', 'expense'), ('Servicios básicos', 'expense'),
                 ('Internet y telefonía', 'expense'), ('Transporte', 'expense'), ('Cafés y snacks', 'expense'),
                 ('Comida a domicilio', 'expense'), ('Compras pequeñas', 'expense'), ('Entretenimiento', 'expense'),
                 ('Suscripciones', 'expense'), ('Salud', 'expense'), ('Deudas', 'expense')]
        for name, kind in names:
            row = one(conn, '''INSERT INTO categories(user_id,name,kind) VALUES(%s,%s,%s)
                ON CONFLICT(user_id,name,kind) DO NOTHING RETURNING id''', (uid, name, kind))
            if row:
                created['categories'] += 1
            else:
                row = one(conn, 'SELECT id FROM categories WHERE user_id=%s AND name=%s AND kind=%s', (uid, name, kind))
            category_ids[name] = row['id']

        def obligation(category, title, amount, due, payments=(), voided=False):
            row = one(conn, '''INSERT INTO obligations(user_id,category_id,title,planned,due_date,voided)
                VALUES(%s,%s,%s,%s,%s,%s) RETURNING id''',
                (uid, category_ids[category], title, amount, due, voided))
            created['obligations'] += 1
            paid_total = Decimal(0)
            for value, paid_on in payments:
                value = Decimal(str(value))
                if paid_on > CUTOFF or value <= 0 or voided:
                    raise ValueError('Movimiento inicial inválido.')
                paid_total += value
                if paid_total > Decimal(str(amount)):
                    raise ValueError('Los pagos iniciales superan el compromiso.')
                conn.execute('INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,%s)',
                             (row['id'], value, paid_on))
                created['payments'] += 1
            return row['id']

        def paid(category, title, amount, when):
            return obligation(category, title, amount, when, [(amount, when)])

        for month in (9, 10):
            prefix = f'{month:02}/2026'
            def d(day):
                return date(2026, month, day)
            paid('Sueldo', f'Nómina {prefix} · empleo administrativo', 6000, d(1))
            paid('Freelance', f'Diseño gráfico {prefix} · cliente independiente', 900 if month == 9 else 1250, d(25))
            # La vivienda tiene dos abonos para probar agregados sin duplicar el principal.
            obligation('Vivienda', f'Alquiler {prefix}', 1500, d(5), [(1000, d(3)), (500, d(5))])
            for index, day in enumerate((4, 11, 18, 25), 1):
                paid('Alimentación', f'Supermercado {prefix} · semana {index}', 225 if month == 9 else 250, d(day))
            for category, title, amount, day in [
                ('Servicios básicos', 'Electricidad', 180 if month == 9 else 200, 12),
                ('Servicios básicos', 'Agua', 55, 12), ('Servicios básicos', 'Gas', 90, 20),
                ('Internet y telefonía', 'Internet hogar', 220, 10),
                ('Internet y telefonía', 'Plan telefónico', 100, 15),
                ('Universidad', 'Mensualidad universitaria', 900, 5),
                ('Salud', 'Farmacia' if month == 9 else 'Consulta y medicamentos', 120 if month == 9 else 250, 18),
                ('Suscripciones', 'Streaming de series', 89, 8),
                ('Suscripciones', 'Música sin anuncios', 69, 18)]:
                paid(category, f'{title} {prefix}', amount, d(day))
            small = [
                ('Transporte', 'Bus al trabajo', 12, 12),
                ('Cafés y snacks', 'Café antes de trabajar', 12 if month == 9 else 18, 18 if month == 9 else 20),
                ('Cafés y snacks', 'Snack de oficina', 10 if month == 9 else 14, 12 if month == 9 else 15),
                ('Comida a domicilio', 'Pedido de cena por aplicación', 6 if month == 9 else 8, 58 if month == 9 else 65),
                ('Transporte', 'Taxi por salir tarde', 4 if month == 9 else 6, 35 if month == 9 else 40),
                ('Compras pequeñas', 'Compra impulsiva en tienda', 8 if month == 9 else 10, 22 if month == 9 else 28),
                ('Entretenimiento', 'Salida de fin de semana', 2, 90 if month == 9 else 100)]
            for category, title, count, amount in small:
                for index in range(count):
                    day = 2 + (index * 3) % 27
                    paid(category, f'{title} {prefix} · {index + 1:02}', amount, d(day))

        # Cada deuda aparece una sola vez como compromiso total. Las cuotas son
        # payments de ese mismo registro, nunca nuevas obligaciones de principal.
        for title, principal, september, october in [
            ('Préstamo familiar · compromiso total sin cronograma', 900, 150, 200),
            ('Compra de computadora · compromiso total sin cronograma', 2500, 250, 200),
            ('Préstamo personal · compromiso total sin cronograma', 6000, 350, 350)]:
            obligation('Deudas', title, principal, date(2026, 11, 30),
                       [(september, date(2026, 9, 15)), (october, date(2026, 10, 15))])

        # Noviembre reutiliza sueldo, alimentación y universidad de la semilla.
        # Las pequeñas compras ya realizadas permiten contrastar el mes parcial.
        for category, title, amount, day in [
            ('Cafés y snacks', 'Café antes de trabajar · noviembre 01', 20, 1),
            ('Cafés y snacks', 'Café antes de trabajar · noviembre 02', 20, 2),
            ('Cafés y snacks', 'Snack de oficina · noviembre 01', 15, 1),
            ('Cafés y snacks', 'Snack de oficina · noviembre 02', 15, 2),
            ('Comida a domicilio', 'Pedido de cena por aplicación · noviembre 01', 65, 1),
            ('Transporte', 'Taxi por salir tarde · noviembre 01', 40, 1),
            ('Transporte', 'Bus al trabajo · noviembre 01', 12, 1),
            ('Transporte', 'Bus al trabajo · noviembre 02', 12, 2),
            ('Compras pequeñas', 'Compra impulsiva en tienda · noviembre 02', 28, 2)]:
            paid(category, title, amount, date(2026, 11, day))
        for category, title, amount, day in [
            ('Vivienda', 'Alquiler noviembre · previsto', 1500, 5),
            ('Servicios básicos', 'Electricidad noviembre · prevista', 200, 12),
            ('Servicios básicos', 'Agua noviembre · prevista', 55, 12),
            ('Servicios básicos', 'Gas noviembre · previsto', 90, 20),
            ('Internet y telefonía', 'Internet hogar noviembre · previsto', 220, 10),
            ('Internet y telefonía', 'Plan telefónico noviembre · previsto', 100, 15),
            ('Suscripciones', 'Streaming de series noviembre · previsto', 89, 8),
            ('Suscripciones', 'Música sin anuncios noviembre · prevista', 69, 18),
            ('Alimentación', 'Compra adicional de supermercado noviembre · prevista', 250, 9),
            ('Salud', 'Control médico noviembre · previsto', 250, 18),
            ('Freelance', 'Diseño gráfico noviembre · cobro aún no confirmado', 700, 25)]:
            obligation(category, title, amount, date(2026, 11, day))
        obligation('Transporte', 'Reparación de frenos de bicicleta · anticipo', 300, date(2026, 11, 12),
                   [(50, date(2026, 11, 2))])
        obligation('Compras pequeñas', 'Audífonos descartados · compra anulada', 450, date(2026, 11, 25), voided=True)

        templates = [('Sueldo', 'Nómina mensual', 6000, True),
                     ('Vivienda', 'Alquiler mensual', 1500, True),
                     ('Universidad', 'Mensualidad universitaria', 900, True),
                     ('Internet y telefonía', 'Internet hogar mensual', 220, True),
                     ('Internet y telefonía', 'Plan telefónico mensual', 100, True),
                     ('Suscripciones', 'Streaming de series mensual', 89, True),
                     ('Suscripciones', 'Música sin anuncios mensual', 69, True),
                     ('Suscripciones', 'Gimnasio cancelado · plantilla inactiva', 180, False)]
        for category, title, amount, active in templates:
            conn.execute('''INSERT INTO recurring(user_id,category_id,title,amount,start_month,active)
                VALUES(%s,%s,%s,%s,%s,%s)''',
                (uid, category_ids[category], title, amount, date(2026, 12, 1), active))
            created['recurring'] += 1

        goal_specs = [
            ('Fondo de emergencia', 5000, date(2027, 4, 30), True,
             [(200, date(2026, 9, 5)), (150, date(2026, 10, 2)), (-300, date(2026, 10, 20))]),
            ('Computadora para trabajo freelance', 4500, date(2027, 2, 28), True,
             [(150, date(2026, 9, 12)), (150, date(2026, 10, 12)), (100, date(2026, 11, 2))]),
            ('Diplomado para mejorar ingresos', 1800, date(2027, 1, 31), True,
             [(100, date(2026, 9, 16)), (50, date(2026, 10, 16))]),
            ('Viaje pospuesto · meta inactiva', 1200, date(2027, 8, 31), False,
             [(50, date(2026, 9, 20)), (-50, date(2026, 10, 21))]),
            ('Curso corto completado', 25, date(2026, 11, 30), True,
             [(25, date(2026, 11, 2))]),
            ('Renovación de equipo · plazo vencido', 600, date(2026, 10, 31), True, [])]
        for name, target, deadline, active, movements in goal_specs:
            goal = one(conn, 'SELECT id FROM goals WHERE user_id=%s AND name=%s ORDER BY id LIMIT 1', (uid, name))
            if not goal:
                goal = one(conn, '''INSERT INTO goals(user_id,name,target,deadline,active)
                    VALUES(%s,%s,%s,%s,%s) RETURNING id''', (uid, name, target, deadline, active))
                created['goals'] += 1
            existing = many(conn, 'SELECT amount,moved_on FROM savings WHERE goal_id=%s', (goal['id'],))
            timeline = [(row['moved_on'], row['amount']) for row in existing]
            timeline += [(when, Decimal(str(amount))) for amount, when in movements]
            balance = Decimal(0)
            for when, amount in sorted(timeline, key=lambda item: (item[0], -item[1])):
                balance += amount
                if balance < 0 or when > CUTOFF:
                    raise ValueError('La línea temporal de ahorro no admite sobregiro ni movimientos futuros.')
            for amount, when in movements:
                conn.execute('INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,%s,%s)', (goal['id'], amount, when))
                created['savings'] += 1

        conn.execute('INSERT INTO audit(actor_id,action,entity,entity_id) VALUES(%s,%s,%s,%s)',
                     (uid, VERSION, 'demo_scenario', str(uid)))
        return _summary(conn, uid, created, normalized, False)


def main():
    with db() as conn:
        result = populate_demo(conn)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()

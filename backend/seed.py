import os
from datetime import date
from .db import db,one
from .security import password_hash


def seed():
    for key in ('ADMIN_PASSWORD','DEMO_PASSWORD','BI_PASSWORD'):
        if len(os.getenv(key,''))<16 or os.environ[key].startswith('CAMBIAR'):
            raise RuntimeError('Configura contraseñas independientes de al menos 16 caracteres en .env')
    with db() as conn:
        for email,name,role,key in [('admin@example.test','Administración','admin','ADMIN_PASSWORD'),
                                     ('demo@example.test','Ana · datos ficticios','user','DEMO_PASSWORD'),
                                     ('bi@example.test','Lectura de reportes','bi','BI_PASSWORD')]:
            conn.execute('INSERT INTO users(email,name,password_hash,role) VALUES(%s,%s,%s,%s) ON CONFLICT(email) DO NOTHING',
                         (email,name,password_hash(os.environ[key]),role))
        for ident,name in [('rag','Consulta tus finanzas'),('budget','Analiza tu presupuesto'),('goals','Explora tus metas')]:
            conn.execute('INSERT INTO services(id,name) VALUES(%s,%s) ON CONFLICT DO NOTHING',(ident,name))
        if not one(conn,'SELECT id FROM knowledge LIMIT 1'):
            conn.execute('INSERT INTO knowledge(title,body,source) VALUES(%s,%s,%s)',
                ('Presupuesto y ahorro','Un presupuesto distingue ingresos, egresos y aportes a ahorro. El aporte a ahorro mueve dinero disponible a un fondo y no constituye consumo. Los pagos parciales reducen el saldo de una obligación. Los escenarios de metas no garantizan resultados.',
                 'Guía educativa interna del prototipo académico'))
        uid=one(conn,"SELECT id FROM users WHERE email='demo@example.test'")['id']
        for name,kind in [('Sueldo','income'),('Alimentación','expense'),('Universidad','expense')]:
            conn.execute('INSERT INTO categories(user_id,name,kind) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(uid,name,kind))
        if not one(conn,'SELECT id FROM obligations WHERE user_id=%s LIMIT 1',(uid,)):
            for name,title,amount in [('Sueldo','Sueldo de noviembre ficticio','6000.00'),('Alimentación','Alimentación noviembre','1000.00'),('Universidad','Universidad noviembre','900.00')]:
                cat=one(conn,'SELECT id FROM categories WHERE user_id=%s AND name=%s',(uid,name))['id']
                ob=one(conn,"INSERT INTO obligations(user_id,category_id,title,planned,due_date) VALUES(%s,%s,%s,%s,'2026-11-05') RETURNING id",(uid,cat,title,amount))
                paid=amount if name!='Universidad' else '400.00'
                conn.execute("INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,'2026-11-05')",(ob['id'],paid))
        if not one(conn,'SELECT id FROM goals WHERE user_id=%s LIMIT 1',(uid,)):
            goal=one(conn,"INSERT INTO goals(user_id,name,target,deadline) VALUES(%s,'Fondo de emergencia','5000.00','2027-04-30') RETURNING id",(uid,))
            conn.execute("INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,'500.00','2026-11-05')",(goal['id'],))
    print('Seed ficticio completado. No se imprimen contraseñas. Usuarios: admin@example.test, demo@example.test, bi@example.test.')


if __name__=='__main__': seed()

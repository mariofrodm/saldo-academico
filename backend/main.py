import os
import secrets
import time
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder, ENCODERS_BY_TYPE
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from .db import db, one, many, money, audit
from .security import current_user, admin, report_user, fingerprint, password_ok, password_hash
from .domain import owned, board, finance_summary, goal_rows
from .reports import router as reports_router

ENCODERS_BY_TYPE[Decimal]=str


class DecimalResponse(JSONResponse):
    def render(self, content):
        return super().render(jsonable_encoder(content, custom_encoder={Decimal: str}))


app=FastAPI(title='Saldo · API académica',version='1.0.0',default_response_class=DecimalResponse)
app.include_router(reports_router)

from psycopg.errors import UniqueViolation, ForeignKeyViolation

@app.exception_handler(UniqueViolation)
async def duplicate(request, exc):
    return JSONResponse(status_code=409,content={'detail':'El registro ya existe; actualiza la vista'})

@app.exception_handler(ForeignKeyViolation)
async def referenced(request, exc):
    return JSONResponse(status_code=409,content={'detail':'Hay registros relacionados; usa inactivación'})


@app.middleware('http')
async def headers(request: Request, call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'" if not request.url.path.startswith('/docs') else "frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Login(Strict):
    email: str=Field(min_length=3,max_length=160)
    password: str=Field(min_length=1,max_length=128)

class Category(Strict):
    name: str=Field(min_length=1,max_length=80)
    kind: str=Field(pattern='^(income|expense)$')
    active: bool=True

class Obligation(Strict):
    category_id: int
    title: str=Field(min_length=1,max_length=160)
    planned: Decimal=Field(gt=0,max_digits=15,decimal_places=2)
    due_date: date

class Payment(Strict):
    amount: Decimal=Field(gt=0,max_digits=15,decimal_places=2)
    paid_on: date

class Goal(Strict):
    name: str=Field(min_length=1,max_length=100)
    target: Decimal=Field(gt=0,max_digits=15,decimal_places=2)
    deadline: date
    active: bool=True

class Movement(Strict):
    amount: Decimal=Field(max_digits=15,decimal_places=2)
    moved_on: date

class Recurring(Strict):
    category_id: int
    title: str=Field(min_length=1,max_length=160)
    amount: Decimal=Field(gt=0,max_digits=15,decimal_places=2)
    start_month: date
    active: bool=True

class UserCreate(Strict):
    email: str=Field(min_length=3,max_length=160,pattern=r'^\S+@\S+\.\S+$')
    name: str=Field(min_length=1,max_length=100)
    password: str=Field(min_length=12,max_length=128)
    role: str=Field(default='user',pattern='^(admin|user|bi)$')
    token_limit: int=Field(default=20000,ge=0,le=100000)
    bi_scope: int|None=None

class UserUpdate(Strict):
    name: str=Field(min_length=1,max_length=100)
    active: bool
    token_limit: int=Field(ge=0,le=100000)

class Knowledge(Strict):
    title: str=Field(min_length=1,max_length=160)
    body: str=Field(min_length=1,max_length=3000)
    source: str=Field(min_length=1,max_length=300)
    active: bool=True

class Service(Strict):
    enabled: bool
    model: str=Field(pattern=r'^[a-zA-Z0-9/_\-.]{1,100}$')
    max_output: int=Field(ge=128,le=768)
    max_rounds: int=Field(ge=2,le=6)


attempts=defaultdict(deque)


@app.get('/api/health',tags=['Sistema'])
def health():
    with db() as conn:
        one(conn,'SELECT 1')
    return {'status':'ok','database':'ok','commit':os.getenv('RENDER_GIT_COMMIT') or os.getenv('BUILD_SHA','local')}


@app.post('/api/v1/auth/login',tags=['Autenticación'])
def login(body: Login, request: Request, response: Response):
    key=fingerprint((request.client.host if request.client else '')+body.email.lower())
    now=time.monotonic()
    if len(attempts)>1000:
        for k in list(attempts):
            if not attempts[k] or attempts[k][-1]<now-900: del attempts[k]
    history=attempts[key]
    while history and history[0]<now-900: history.popleft()
    if len(history)>=8: raise HTTPException(429,'Demasiados intentos; espera 15 minutos')
    history.append(now)
    with db() as conn:
        user=one(conn,'SELECT * FROM users WHERE email=%s AND active',(body.email.lower(),))
        if not user or user['role']=='bi' or not password_ok(body.password,user['password_hash']):
            raise HTTPException(401,'Credenciales incorrectas')
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(24)
        conn.execute('DELETE FROM sessions WHERE expires_at<now()')
        conn.execute("INSERT INTO sessions VALUES(%s,%s,%s,now()+interval '8 hours')",(fingerprint(token),user['id'],csrf))
    response.set_cookie('saldo_session',token,httponly=True,secure=os.getenv('COOKIE_SECURE','true')=='true',samesite='strict',max_age=28800)
    return {'access_token':token,'token_type':'bearer','csrf':csrf}


@app.post('/api/v1/auth/logout',tags=['Autenticación'])
def logout(request: Request,response: Response,user=Depends(current_user)):
    token=request.headers.get('authorization','')[7:] or request.cookies.get('saldo_session','')
    with db() as conn: conn.execute('DELETE FROM sessions WHERE token_hash=%s',(fingerprint(token),))
    response.delete_cookie('saldo_session')
    return {'ok':True}


@app.get('/api/v1/me',tags=['Autenticación'])
def me(user=Depends(current_user)):
    return {k:user[k] for k in ('id','email','name','role','token_limit','tokens_used','tokens_reserved','csrf')}


@app.get('/api/v1/categories',tags=['Finanzas'])
def categories(user=Depends(current_user)):
    with db() as conn: return many(conn,'SELECT * FROM categories WHERE user_id=%s ORDER BY name',(user['id'],))


@app.post('/api/v1/categories',tags=['Finanzas'])
def category_create(body:Category,user=Depends(current_user)):
    with db() as conn:
        if one(conn,'SELECT id FROM categories WHERE user_id=%s AND lower(name)=lower(%s) AND kind=%s',(user['id'],body.name.strip(),body.kind)):
            raise HTTPException(409,'Categoría existente')
        return one(conn,'INSERT INTO categories(user_id,name,kind,active) VALUES(%s,%s,%s,%s) RETURNING *',(user['id'],body.name.strip(),body.kind,body.active))


@app.put('/api/v1/categories/{ident}',tags=['Finanzas'])
def category_update(ident:int,body:Category,user=Depends(current_user)):
    with db() as conn:
        old=owned(conn,'categories',ident,user)
        if old['kind']!=body.kind and one(conn,'SELECT id FROM obligations WHERE category_id=%s LIMIT 1',(ident,)):
            raise HTTPException(409,'No se cambia naturaleza de una categoría con historial')
        if one(conn,'SELECT id FROM categories WHERE user_id=%s AND lower(name)=lower(%s) AND kind=%s AND id<>%s',(user['id'],body.name.strip(),body.kind,ident)):
            raise HTTPException(409,'Categoría existente')
        audit(conn,user,'update','categories',ident)
        return one(conn,'UPDATE categories SET name=%s,kind=%s,active=%s WHERE id=%s RETURNING *',(body.name.strip(),body.kind,body.active,ident))


@app.get('/api/v1/board',tags=['Finanzas'])
def board_get(month:date,user=Depends(current_user)):
    import calendar
    start=month.replace(day=1); end=month.replace(day=calendar.monthrange(month.year,month.month)[1])
    with db() as conn:
        return {'items':board(conn,user['id'],start),'summary':finance_summary(conn,user['id'],start,end)}


@app.post('/api/v1/obligations',tags=['Finanzas'])
def obligation_create(body:Obligation,user=Depends(current_user)):
    with db() as conn:
        if not owned(conn,'categories',body.category_id,user)['active']: raise HTTPException(409,'Categoría inactiva')
        return one(conn,'INSERT INTO obligations(user_id,category_id,title,planned,due_date) VALUES(%s,%s,%s,%s,%s) RETURNING *',
                   (user['id'],body.category_id,body.title,body.planned,body.due_date))


@app.put('/api/v1/obligations/{ident}',tags=['Finanzas'])
def obligation_update(ident:int,body:Obligation,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'obligations',ident,user); owned(conn,'categories',body.category_id,user)
        if one(conn,'SELECT id FROM payments WHERE obligation_id=%s LIMIT 1',(ident,)): raise HTTPException(409,'La edición está bloqueada porque el compromiso ya tiene pagos registrados')
        audit(conn,user,'update','obligations',ident)
        return one(conn,'UPDATE obligations SET category_id=%s,title=%s,planned=%s,due_date=%s WHERE id=%s RETURNING *',
                   (body.category_id,body.title,body.planned,body.due_date,ident))


@app.delete('/api/v1/obligations/{ident}',tags=['Finanzas'])
def obligation_void(ident:int,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'obligations',ident,user)
        if one(conn,'SELECT id FROM payments WHERE obligation_id=%s LIMIT 1',(ident,)): raise HTTPException(409,'No se anulan obligaciones con pagos registrados')
        conn.execute('UPDATE obligations SET voided=true WHERE id=%s',(ident,)); audit(conn,user,'void','obligations',ident)
    return {'ok':True}


@app.post('/api/v1/obligations/{ident}/payments',tags=['Finanzas'])
def pay(ident:int,body:Payment,user=Depends(current_user)):
    with db() as conn:
        ob=owned(conn,'obligations',ident,user)
        paid=one(conn,'SELECT coalesce(sum(amount),0) AS total FROM payments WHERE obligation_id=%s',(ident,))['total']
        if ob['voided'] or paid+body.amount>ob['planned']: raise HTTPException(409,'Abono excede saldo o registro anulado')
        return one(conn,'INSERT INTO payments(obligation_id,amount,paid_on) VALUES(%s,%s,%s) RETURNING *',(ident,body.amount,body.paid_on))


@app.get('/api/v1/recurring',tags=['Finanzas'])
def recurring_list(user=Depends(current_user)):
    with db() as conn: return many(conn,'SELECT * FROM recurring WHERE user_id=%s ORDER BY id',(user['id'],))


@app.post('/api/v1/recurring',tags=['Finanzas'])
def recurring_create(body:Recurring,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'categories',body.category_id,user)
        return one(conn,'INSERT INTO recurring(user_id,category_id,title,amount,start_month,active) VALUES(%s,%s,%s,%s,%s,%s) RETURNING *',
                   (user['id'],body.category_id,body.title,body.amount,body.start_month.replace(day=1),body.active))


@app.put('/api/v1/recurring/{ident}',tags=['Finanzas'])
def recurring_update(ident:int,body:Recurring,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'recurring',ident,user); owned(conn,'categories',body.category_id,user)
        # Existing instances are snapshots. Editing applies only to uninstantiated months.
        row=one(conn,'UPDATE recurring SET title=%s,amount=%s,category_id=%s,active=%s WHERE id=%s RETURNING *',
                (body.title,body.amount,body.category_id,body.active,ident))
        audit(conn,user,'update','recurring',ident)
        return row


@app.get('/api/v1/goals',tags=['Ahorro'])
def goals(user=Depends(current_user)):
    with db() as conn: return goal_rows(conn,user['id'])


@app.post('/api/v1/goals',tags=['Ahorro'])
def goal_create(body:Goal,user=Depends(current_user)):
    with db() as conn: return one(conn,'INSERT INTO goals(user_id,name,target,deadline,active) VALUES(%s,%s,%s,%s,%s) RETURNING *',
                                 (user['id'],body.name,body.target,body.deadline,body.active))


@app.put('/api/v1/goals/{ident}',tags=['Ahorro'])
def goal_update(ident:int,body:Goal,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'goals',ident,user); audit(conn,user,'update','goals',ident)
        return one(conn,'UPDATE goals SET name=%s,target=%s,deadline=%s,active=%s WHERE id=%s RETURNING *',
                   (body.name,body.target,body.deadline,body.active,ident))


@app.get('/api/v1/goals/{ident}/movements',tags=['Ahorro'])
def movements(ident:int,user=Depends(current_user)):
    with db() as conn:
        owned(conn,'goals',ident,user)
        return many(conn,'SELECT * FROM savings WHERE goal_id=%s ORDER BY moved_on,id',(ident,))


@app.post('/api/v1/goals/{ident}/movements',tags=['Ahorro'])
def movement_create(ident:int,body:Movement,user=Depends(current_user)):
    with db() as conn:
        goal=owned(conn,'goals',ident,user)
        balance=one(conn,'SELECT coalesce(sum(amount),0) AS total FROM savings WHERE goal_id=%s',(ident,))['total']
        if not goal['active'] or not body.amount or balance+body.amount<0: raise HTTPException(409,'Fondo inactivo, monto cero o retiro superior al saldo')
        return one(conn,'INSERT INTO savings(goal_id,amount,moved_on) VALUES(%s,%s,%s) RETURNING *',(ident,body.amount,body.moved_on))


@app.get('/api/v1/services',tags=['IA'])
def services(user=Depends(current_user)):
    with db() as conn: return {'items':many(conn,'SELECT * FROM services ORDER BY id'),'provider_ready':bool(os.getenv('GROQ_API_KEY'))}


@app.get('/api/v1/admin/users',tags=['Administración'])
def users(user=Depends(admin)):
    with db() as conn: return many(conn,'SELECT id,email,name,role,active,token_limit,tokens_used,tokens_reserved,bi_scope FROM users ORDER BY id')


@app.post('/api/v1/admin/users',tags=['Administración'])
def user_create(body:UserCreate,user=Depends(admin)):
    with db() as conn:
        if one(conn,'SELECT id FROM users WHERE email=%s',(body.email.lower(),)): raise HTTPException(409,'Correo existente')
        if body.bi_scope and not one(conn,"SELECT id FROM users WHERE id=%s AND role IN ('admin','user')",(body.bi_scope,)): raise HTTPException(422,'Alcance BI inválido')
        row=one(conn,'INSERT INTO users(email,name,password_hash,role,token_limit,bi_scope) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id',
                (body.email.lower(),body.name,password_hash(body.password),body.role,body.token_limit,body.bi_scope))
        audit(conn,user,'create','users',row['id']); return row


@app.put('/api/v1/admin/users/{ident}',tags=['Administración'])
def user_update(ident:int,body:UserUpdate,user=Depends(admin)):
    with db() as conn:
        if ident==user['id'] and not body.active: raise HTTPException(409,'No puedes desactivarte')
        if not one(conn,'SELECT id FROM users WHERE id=%s FOR UPDATE',(ident,)): raise HTTPException(404,'Usuario inexistente')
        conn.execute('UPDATE users SET name=%s,active=%s,token_limit=%s WHERE id=%s',(body.name,body.active,body.token_limit,ident))
        audit(conn,user,'update','users',ident)
    return {'ok':True}


@app.get('/api/v1/admin/knowledge',tags=['Administración'])
def knowledge(user=Depends(admin)):
    with db() as conn: return many(conn,'SELECT * FROM knowledge ORDER BY id')


@app.post('/api/v1/admin/knowledge',tags=['Administración'])
def knowledge_create(body:Knowledge,user=Depends(admin)):
    with db() as conn:
        row=one(conn,'INSERT INTO knowledge(title,body,source,active) VALUES(%s,%s,%s,%s) RETURNING *',(body.title,body.body,body.source,body.active))
        audit(conn,user,'create','knowledge',row['id']); return row


@app.put('/api/v1/admin/knowledge/{ident}',tags=['Administración'])
def knowledge_update(ident:int,body:Knowledge,user=Depends(admin)):
    with db() as conn:
        row=one(conn,'UPDATE knowledge SET title=%s,body=%s,source=%s,active=%s WHERE id=%s RETURNING *',(body.title,body.body,body.source,body.active,ident))
        if not row: raise HTTPException(404,'Documento inexistente')
        audit(conn,user,'update','knowledge',ident); return row


@app.put('/api/v1/admin/services/{ident}',tags=['Administración'])
def service_update(ident:str,body:Service,user=Depends(admin)):
    with db() as conn:
        row=one(conn,'UPDATE services SET enabled=%s,model=%s,max_output=%s,max_rounds=%s WHERE id=%s RETURNING *',
                (body.enabled,body.model,body.max_output,body.max_rounds,ident))
        if not row: raise HTTPException(404,'Servicio inexistente')
        audit(conn,user,'update','services',ident); return row


from .ai import router as ai_router
app.include_router(ai_router)
static=Path(__file__).resolve().parent.parent/'frontend'/'dist'
if static.exists():
    app.mount('/assets',StaticFiles(directory=static/'assets'),name='assets')
    @app.get('/',include_in_schema=False)
    def index(): return FileResponse(static/'index.html')

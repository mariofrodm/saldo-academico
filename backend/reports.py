from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from .db import db, many, one
from .security import report_user

router = APIRouter(prefix='/api/v1/reports', tags=['Reportes'])


def filters(user, date_from, date_to, service, user_id, as_of):
    if date_from and date_to and date_from>date_to:
        raise HTTPException(422, 'Rango inválido')
    if as_of.tzinfo is None:
        raise HTTPException(422, 'as_of requiere zona horaria')
    clauses, params = ['r.finished_at<=%s'], [as_of]
    allowed = user['id'] if user['role']=='user' else user.get('bi_scope')
    if allowed is not None:
        if user_id is not None and user_id!=allowed:
            raise HTTPException(403, 'Filtro fuera de tu alcance')
        user_id = allowed
    for condition, value in [("(r.created_at AT TIME ZONE 'America/Guatemala')::date>=%s", date_from),
                              ("(r.created_at AT TIME ZONE 'America/Guatemala')::date<=%s", date_to),
                              ('r.service=%s', service), ('r.user_id=%s', user_id)]:
        if value is not None:
            clauses.append(condition); params.append(value)
    return ' AND '.join(clauses), params


BASE = '''SELECT r.id,r.user_id,r.service,r.status,r.created_at,
             (r.created_at AT TIME ZONE 'America/Guatemala')::date AS report_date,
             count(c.id) AS provider_calls,coalesce(sum(c.input_tokens),0)::bigint AS input_tokens,
             coalesce(sum(c.output_tokens),0)::bigint AS output_tokens,
             coalesce(sum(c.input_tokens+c.output_tokens),0)::bigint AS total_tokens
          FROM requests r LEFT JOIN provider_calls c ON c.request_id=r.id'''


@router.get('/usage')
def usage(date_from: date|None=None, date_to: date|None=None, service: str|None=None,
          user_id: int|None=None, as_of: datetime|None=None, after: str|None=None,
          page_size: int=Query(100,ge=1,le=500), user=Depends(report_user)):
    cutoff = as_of or datetime.now(timezone.utc)
    where, params = filters(user,date_from,date_to,service,user_id,cutoff)
    if after:
        try:
            stamp, ident = after.split('|',1)
            from uuid import UUID
            params += [datetime.fromisoformat(stamp), UUID(ident)]
        except (ValueError, TypeError):
            raise HTTPException(422,'Cursor inválido')
        where += ' AND (r.created_at,r.id)>(%s,%s)'
    with db() as conn:
        rows = many(conn, BASE+' WHERE '+where+' GROUP BY r.id ORDER BY r.created_at,r.id LIMIT %s', params+[page_size+1])
    extra, rows = len(rows)>page_size, rows[:page_size]
    cursor = rows[-1]['created_at'].isoformat()+'|'+str(rows[-1]['id']) if rows and extra else None
    return {'items':rows,'next_cursor':cursor,'as_of':cutoff}


@router.get('/summary')
def summary(date_from: date|None=None, date_to: date|None=None, service: str|None=None,
            user_id: int|None=None, as_of: datetime|None=None, user=Depends(report_user)):
    cutoff=as_of or datetime.now(timezone.utc)
    where, params=filters(user,date_from,date_to,service,user_id,cutoff)
    with db() as conn:
        rows=many(conn, '''SELECT service,count(*) AS requests,sum(provider_calls)::bigint AS provider_calls,
                        sum(input_tokens)::bigint AS input_tokens,sum(output_tokens)::bigint AS output_tokens,
                        sum(total_tokens)::bigint AS total_tokens FROM ('''+BASE+' WHERE '+where+
                        ' GROUP BY r.id) q GROUP BY service ORDER BY service',params)
    return {'items':rows,'as_of':cutoff}

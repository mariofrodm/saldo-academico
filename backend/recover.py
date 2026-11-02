from .db import db,one,many


def recover_stale():
    count=0
    with db() as conn:
        candidates=many(conn,"""SELECT id,user_id FROM requests WHERE status='running'
                  AND (pending_started<now()-interval '15 minutes'
                    OR (pending_tokens=0 AND created_at<now()-interval '30 minutes')) LIMIT 100""")
        for candidate in candidates:
            one(conn,'SELECT id FROM users WHERE id=%s FOR UPDATE',(candidate['user_id'],))
            row=one(conn,"SELECT * FROM requests WHERE id=%s AND status='running' FOR UPDATE",(candidate['id'],))
            if not row: continue
            amount=row['pending_tokens']
            if amount:
                conn.execute('UPDATE users SET tokens_reserved=tokens_reserved-%s,tokens_used=tokens_used+%s WHERE id=%s',
                             (amount,amount,row['user_id']))
                for period in (row['pending_day'],row['pending_minute']):
                    conn.execute('UPDATE budgets SET reserved=reserved-%s,used=used+%s WHERE period=%s',(amount,amount,period))
                conn.execute("INSERT INTO provider_calls(request_id,model,input_tokens,output_tokens,usage_kind) VALUES(%s,%s,%s,0,'reserved_unknown')",
                             (row['id'],row['pending_model'],amount))
            conn.execute("""UPDATE requests SET pending_tokens=0,pending_started=NULL,status='failed',
                       error_code='interrupted',response='Solicitud interrumpida. El uso no confirmado se conserva como estimación conservadora.',
                       finished_at=now() WHERE id=%s""",(row['id'],))
            count+=1
    return count


if __name__=='__main__': print('Solicitudes interrumpidas conciliadas:',recover_stale())

"""Authenticated, read-only tools shared by agents and external API clients."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from .security import current_user
from . import advisor, diagnosis, planning

router = APIRouter(prefix='/api/v1/advisor', tags=['Asesor: consultas de solo lectura'])


class Query(BaseModel):
    model_config = ConfigDict(extra='forbid')
    arguments: dict


@router.get('/tools')
def available_tools(user=Depends(current_user)):
    return {'read_only': True, 'user_scope': 'authenticated_user',
            'tools': [*advisor.TOOLS.values(), diagnosis.TOOL, planning.TOOL]}


@router.post('/{tool_name}')
def query(tool_name: str, body: Query, user=Depends(current_user)):
    if tool_name not in advisor.TOOLS and tool_name not in ('financial_diagnosis','planning_snapshot'):
        raise HTTPException(404, 'Consulta no disponible')
    try:
        if tool_name == 'financial_diagnosis': return diagnosis.execute(body.arguments, user['id'])
        if tool_name == 'planning_snapshot': return planning.execute(body.arguments, user['id'])
        return advisor.execute(tool_name, body.arguments, user['id'])
    except (ValueError, TypeError, KeyError, OverflowError):
        raise HTTPException(422, 'Argumentos inválidos o registro propio no disponible') from None

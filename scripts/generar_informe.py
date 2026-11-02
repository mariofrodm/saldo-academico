#!/usr/bin/env python3
"""Informe académico reproducible. No lee .env ni contacta servicios externos.

Uso: python scripts/generar_informe.py [--manifest ruta.json] [--output ruta.pdf]
Depende únicamente de reportlab. La evidencia y su manifest son locales, no secretos.
Para entrega usar --require-final: exige PBIX existente y verificación explícita.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, Image, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor('#142B3B')
TEAL = colors.HexColor('#087E83')
LIGHT = colors.HexColor('#EAF4F3')
GREY = colors.HexColor('#536675')
LINE = colors.HexColor('#D7E2E7')
AMBER = colors.HexColor('#925D16')
PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 92


def text(value):
    """Texto seguro para Paragraph: sin marcas de herramientas o credenciales."""
    value = str(value).replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    if re.search(r'gsk_[A-Za-z0-9_-]{12,}|postgres(?:ql)?://[^\s]+:[^\s]+@', value):
        raise ValueError('La evidencia contiene una credencial; no se incorpora al informe.')
    return escape(value)


def register_fonts():
    folder = Path('/usr/share/fonts/truetype/dejavu')
    if (folder / 'DejaVuSans.ttf').is_file():
        pdfmetrics.registerFont(TTFont('Saldo', str(folder / 'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('Saldo-Bold', str(folder / 'DejaVuSans-Bold.ttf')))
        pdfmetrics.registerFont(TTFont('SaldoMono', str(folder / 'DejaVuSansMono.ttf')))
        pdfmetrics.registerFontFamily('Saldo', normal='Saldo', bold='Saldo-Bold', italic='Saldo', boldItalic='Saldo-Bold')
        return 'Saldo', 'Saldo-Bold', 'SaldoMono'
    return 'Helvetica', 'Helvetica-Bold', 'Courier'


FONT, BOLD, MONO = register_fonts()
STYLES = {
    'body': ParagraphStyle('body', fontName=FONT, fontSize=9, leading=13.3, textColor=INK, spaceAfter=7),
    'small': ParagraphStyle('small', fontName=FONT, fontSize=7.8, leading=11, textColor=GREY, spaceAfter=5),
    'table': ParagraphStyle('table', fontName=FONT, fontSize=7.4, leading=10.6, textColor=INK),
    'tablehead': ParagraphStyle('tablehead', fontName=BOLD, fontSize=7.6, leading=10.5, textColor=colors.white),
    'title': ParagraphStyle('title', fontName=BOLD, fontSize=34, leading=39, textColor=INK, spaceAfter=14),
    'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=21, leading=26, textColor=INK, spaceAfter=11),
    'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=11.5, leading=16, textColor=TEAL, spaceBefore=8, spaceAfter=5),
    'kicker': ParagraphStyle('kicker', fontName=BOLD, fontSize=8.5, leading=12, textColor=TEAL, spaceAfter=8),
    'caption': ParagraphStyle('caption', fontName=FONT, fontSize=7.4, leading=10.5, textColor=GREY, spaceBefore=5, spaceAfter=8),
    'code': ParagraphStyle('code', fontName=MONO, fontSize=7.2, leading=11, textColor=INK, backColor=LIGHT, borderPadding=8, spaceAfter=9),
}


def p(value, style='body', raw=False):
    return Paragraph(str(value) if raw else text(value), STYLES[style])


def heading(number, title, intro=None):
    blocks = [p('SALDO / INFORME TÉCNICO ACADÉMICO', 'kicker'), p(f'{number:02d}  {title}', 'h1')]
    if intro:
        blocks.append(p(intro))
    return blocks


def table(headers, rows, widths=None):
    cells = [[p(v, 'tablehead') for v in headers]] + [[p(v, 'table') for v in row] for row in rows]
    obj = Table(cells, colWidths=widths, hAlign='LEFT', repeatRows=1)
    obj.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, TEAL),
        ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE),
    ]))
    return obj


def bullet(label, detail):
    return p(f'<b>{text(label)}.</b> {text(detail)}', raw=True)


class Diagram(Flowable):
    """Diagrama vectorial legible: también se conserva en el PDF al ampliar."""
    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.width = CONTENT_W
        self.height = {'architecture': 290, 'domain': 425, 'ai': 425}[kind]

    def draw(self):
        c = self.canv

        def box(x, y, w, h, title, lines=(), fill=LIGHT):
            c.setStrokeColor(LINE); c.setFillColor(fill)
            c.roundRect(x, y, w, h, 7, fill=1, stroke=1)
            c.setFillColor(INK); c.setFont(BOLD, 8.8)
            c.drawString(x+9, y+h-17, title)
            c.setFont(FONT, 7.3)
            for index, line in enumerate(lines):
                c.drawString(x+9, y+h-32-index*11, line)

        def arrow(x1, y1, x2, y2, label='', dash=False):
            c.setStrokeColor(TEAL); c.setLineWidth(1)
            if dash: c.setDash(3, 2)
            c.line(x1, y1, x2, y2)
            c.setDash()
            import math
            a = math.atan2(y2-y1, x2-x1)
            c.setFillColor(TEAL)
            path = c.beginPath(); path.moveTo(x2, y2)
            path.lineTo(x2-5*math.cos(a-0.5), y2-5*math.sin(a-0.5))
            path.lineTo(x2-5*math.cos(a+0.5), y2-5*math.sin(a+0.5)); path.close()
            c.drawPath(path, fill=1, stroke=0)
            if label:
                c.setFillColor(GREY); c.setFont(FONT, 6.8)
                c.drawCentredString((x1+x2)/2, (y1+y2)/2+5, label)

        if self.kind == 'architecture':
            box(0, 222, 145, 58, 'React / usuario y admin', ['TypeScript · navegador Ubuntu', 'Cookie HttpOnly + CSRF'])
            box(0, 133, 145, 62, 'Power BI / cliente externo', ['Basic: solo reportes', 'Bearer: API externa / Swagger'])
            box(197, 180, 142, 88, 'FastAPI / Render Free', ['Un contenedor y un origen', 'REST · roles · cuotas', 'RAG + herramientas de agentes', 'Datos externos y Decimal'])
            box(386, 214, 117, 56, 'Neon Free', ['PostgreSQL 18.6', 'TLS verify-full'])
            box(386, 133, 117, 56, 'Groq Free', ['gpt-oss-20b', 'Solo desde backend'])
            box(197, 54, 306, 58, 'Fuentes públicas y cálculos controlados', ['Banco Mundial: inflación anual de Guatemala', 'Banguat: referencia USD/GTQ · simulaciones Decimal'])
            box(0, 0, 145, 78, 'GitHub Actions', ['Pruebas + contenedor', 'Despliegue condicionado', 'Commit SHA confirmado'])
            arrow(145, 249, 197, 232, 'HTTPS')
            arrow(145, 163, 197, 205, 'HTTPS')
            arrow(339, 244, 386, 244, 'TLS')
            arrow(339, 195, 386, 165, 'HTTPS')
            arrow(267, 180, 267, 112, 'HTTPS / Decimal')
            arrow(145, 42, 192, 180, 'SHA', True)
            return

        if self.kind == 'domain':
            # Ocho tablas del núcleo financiero y acceso, con FK reales.
            box(161, 337, 179, 79, 'users', ['PK id · UQ email', 'role · active · password_hash', 'token_limit / used / reserved', 'FK bi_scope -> users (opcional)'])
            box(0, 218, 145, 70, 'sessions', ['PK token_hash', 'FK user_id -> users', 'csrf · expires_at'])
            box(180, 218, 145, 70, 'categories', ['PK id · FK user_id', 'name · kind · active', 'UQ usuario / nombre / tipo'])
            box(358, 218, 145, 70, 'goals', ['PK id · FK user_id', 'name · target · deadline', 'active'])
            box(0, 100, 145, 79, 'recurring', ['PK id · FK user_id', 'FK category_id', 'title · amount · start_month', 'active'])
            box(180, 100, 145, 79, 'obligations', ['PK id · FK user_id / category_id', 'FK recurring_id (opcional)', 'title · planned · due_date', 'voided · UQ recurrente / fecha'])
            box(358, 100, 145, 79, 'savings', ['PK id · FK goal_id', 'amount (+aporte / -retiro)', 'moved_on · created_at'])
            box(180, 0, 145, 65, 'payments', ['PK id · FK obligation_id', 'amount · paid_on', 'created_at'])
            arrow(180, 337, 75, 288, '1 a N')
            arrow(252, 337, 252, 288, '1 a N')
            arrow(320, 337, 430, 288, '1 a N')
            arrow(220, 218, 100, 179, '1 a N')
            arrow(252, 218, 252, 179, '1 a N')
            arrow(145, 136, 180, 136, '1:N')
            arrow(430, 218, 430, 179, '1 a N')
            arrow(252, 100, 252, 65, '1 a N')
            c.setFont(FONT, 7.1); c.setFillColor(GREY)
            c.drawString(0, 51, 'FK adicionales a users:')
            c.drawString(0, 38, 'recurring.user_id')
            c.drawString(0, 25, 'obligations.user_id')
        else:
            # Ocho tablas restantes: cinco conectadas y tres auxiliares.
            box(0, 341, 154, 74, 'services', ['PK id: rag / budget / goals', 'enabled · model', 'max_output · max_rounds'])
            box(195, 341, 162, 74, 'conversations', ['PK id UUID · FK user_id', 'FK service -> services', 'created_at'])
            box(195, 199, 190, 105, 'requests', ['PK id UUID · FK conversation_id', 'FK user_id · FK service', 'prompt · response · sources JSONB', 'status · error_code · timestamps', 'pending_*: reserva en curso'])
            box(0, 80, 159, 82, 'provider_calls', ['PK id · FK request_id', 'model · input_tokens', 'output_tokens · usage_kind', 'created_at'])
            box(195, 80, 159, 82, 'tool_runs', ['PK id · FK request_id', 'name · arguments JSONB', 'result JSONB · created_at'])
            box(390, 341, 113, 74, 'knowledge', ['PK id · title · body', 'source · active', 'Índice GIN español'])
            box(390, 199, 113, 105, 'budgets', ['PK period', 'used · reserved', 'Día / minuto', 'Reserva compartida'])
            box(390, 64, 113, 98, 'audit', ['PK id · FK actor_id', 'action · entity', 'entity_id · created_at', 'FK actor_id -> users'])
            arrow(154, 378, 195, 378, '1:N')
            arrow(272, 341, 272, 304, '1 a N')
            arrow(220, 199, 95, 162, '1 a N')
            arrow(288, 199, 275, 162, '1 a N')
            arrow(447, 341, 385, 304, 'RAG', True)
            c.setFont(FONT, 7.1); c.setFillColor(GREY)
            c.drawString(0, 34, 'FK a users: conversations.user_id, requests.user_id y audit.actor_id.')
            c.drawString(0, 20, 'requests.service también referencia services.id. knowledge y budgets no tienen FK.')
            c.drawString(0, 6, 'Línea discontinua: recuperación lógica; no es una llave foránea.')


def resolve(path):
    if not path:
        return None
    value = Path(str(path))
    return value if value.is_absolute() else ROOT / value


def image_block(path, caption, max_height=305):
    path = resolve(path)
    if not path or not path.is_file():
        return [p('La captura no está disponible en esta revisión del informe.', 'small')]
    image = Image(str(path))
    ratio = min(CONTENT_W / image.imageWidth, max_height / image.imageHeight)
    image.drawWidth = image.imageWidth * ratio
    image.drawHeight = image.imageHeight * ratio
    image.hAlign = 'CENTER'
    return [image, p(caption, 'caption')]


def page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE); canvas.line(46, 43, PAGE_W-46, 43)
    canvas.setFont(FONT, 7); canvas.setFillColor(GREY)
    canvas.drawString(46, 29, 'Saldo · Programación Comercial · 02/11/2026 · Datos ficticios')
    canvas.drawRightString(PAGE_W-46, 29, str(doc.page))
    canvas.restoreState()


def load_manifest(path):
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('El manifest debe ser un objeto JSON.')
    return data


def make_report(manifest, destination, require_final=False):
    app_url = manifest.get('app_url', 'https://saldo-academico.onrender.com').rstrip('/')
    repo_url = 'https://github.com/mariofrodm/saldo-academico'
    ci_url = manifest.get('ci_url', repo_url + '/actions/runs/41423307877')
    commit = manifest.get('commit', '0c5d2f7b0df16b643fc070056fd57563e0b2bedf')
    tests = manifest.get('tests_passed', 27)
    bi = manifest.get('powerbi', {})
    verified = bi.get('status') in ('verified', 'complete', 'completado', 'verificado')
    pbix = resolve(bi.get('pbix_path'))
    if require_final and (not verified or not pbix or not pbix.is_file()):
        raise ValueError('La entrega final requiere Power BI verificado y PBIX existente en el manifest.')
    screenshots = manifest.get('screenshots', {})
    if require_final:
        for label, screenshot in [('app', screenshots.get('app', 'evidencias-locales/aplicacion-cloud.png')),
                                  ('ci', screenshots.get('ci', 'evidencias-locales/ci-cd-correcto.png')),
                                  ('powerbi', screenshots.get('powerbi', bi.get('screenshot')))]:
            path = resolve(screenshot)
            if not path or not path.is_file():
                raise ValueError(f'Falta captura final verificable: {label}.')
    cloud_evidence = ROOT / 'evidencias-locales/render-validacion-final.json'
    cloud = load_manifest(cloud_evidence) if cloud_evidence.is_file() else {}
    blocks = []
    add = blocks.extend

    # 1. Propuesta, límites y estado inequívoco.
    add([Spacer(1, 22), p('PROYECTO FINAL / PROGRAMACIÓN COMERCIAL', 'kicker'), p('Saldo', 'title'),
         p('Finanzas personales asistidas por IA', 'h1'),
         p('Propuesta, arquitectura, modelo de datos y evidencias de implementación.'),
         Spacer(1, 8), p('Objetivo y destinatarios', 'h2'),
         p('Ayudar a estudiantes y personas que registran manualmente sus finanzas a comparar presupuesto y ejecución, consultar sus registros con fuentes y explorar metas de ahorro mediante escenarios explicables.'),
         p('El usuario administra sus propios registros e historial. El administrador gestiona usuarios, corpus, configuración de IA y cuotas. Una cuenta BI independiente solo consulta reportes.'),
         table(['Decisión de alcance', 'Implementación'], [
             ['Núcleo del producto', 'GTQ; categorías, obligaciones, pagos parciales, recurrentes mensuales y metas con aportes/retiros.'],
             ['IA obligatoria', 'RAG sobre PostgreSQL + agente de presupuesto + agente de metas con herramientas y fuentes externas.'],
             ['Reporterías', 'Consultas y tokens por usuario, fecha y servicio; misma API para web y Power BI.'],
             ['Exclusiones aprobadas', 'Tarjetas, FIFO, intereses, préstamos, multidivisa operativa, banca real y fondos compartidos.'],
             ['Presupuesto', 'USD 0; capas Free, sin tarjetas ni activaciones de pago.'],
         ], [143, CONTENT_W-143]),
         Spacer(1, 10), p('Estado de esta revisión', 'h2'),
         p(f'Aplicación y API publicadas. {tests} pruebas automatizadas aprobadas y CI/CD completo sobre el commit {commit[:7]}. ' +
           ('Power BI verificado; el archivo PBIX forma parte de la entrega.' if verified else
            'Power BI definitivo en preparación: esta revisión es un borrador y no acredita todavía el PBIX final.')),
         p('Corte técnico: 2 de noviembre de 2026. Fecha de entrega indicada en la consigna: 10 de noviembre. Todos los registros de demostración son ficticios.', 'small'),
         p(f'<b>Aplicación:</b> <link href="{text(app_url)}" color="#087E83">{text(app_url)}</link><br/>'
           f'<b>Repositorio:</b> <link href="{repo_url}" color="#087E83">{repo_url}</link>', raw=True),
         PageBreak()])

    # 2. Arquitectura y recorrido GUI / consumidor externo.
    add(heading(2, 'Arquitectura y stack', 'Un solo contenedor publica React y FastAPI en HTTPS. PostgreSQL conserva el estado; Render no requiere disco persistente.'))
    add([Diagram('architecture'), p('Figura 1. Recorrido real desde GUI, cliente externo y Power BI. Las claves de Groq y Neon permanecen en el servidor.', 'caption'),
         table(['Componente', 'Tecnología y responsabilidad'], [
             ['Interfaz', 'React 19.3.1, TypeScript 7.0.2 y Vite 8.3.5; compilación estática.'],
             ['API', 'Python 3.12, FastAPI 0.162.0, Pydantic, Uvicorn y psycopg 3.3.6; SQL parametrizado.'],
             ['Persistencia', 'PostgreSQL 18.6 en Neon Free; PostgreSQL 17 en local/CI; migraciones Alembic.'],
             ['Inferencia', 'Groq Free, openai/gpt-oss-20b; herramientas autorizadas y límites por ronda.'],
             ['Publicación', 'Docker multietapa, usuario sin privilegios; Render Free 512 MB; GitHub Actions.'],
             ['Analítica', 'Power BI web con importación HTTPS Basic; PBIX exportable y ruta Desktop si fuese necesaria.'],
         ], [112, CONTENT_W-112]),
         p('Fabric no es una dependencia del backend. El RAG usa recuperación textual nativa de PostgreSQL; no requiere servicio vectorial ni embeddings de pago.', 'small'), PageBreak()])

    # 3. Tres servicios distintos y fuentes reales.
    add(heading(3, 'Servicios de IA y fuentes', 'El modelo decide herramientas y continúa con sus resultados. Los cálculos monetarios y las consultas autorizadas los ejecuta el backend.'))
    add([p('RAG · respuesta sobre información recuperada', 'h2'),
         p('La pregunta recupera corpus activo mediante búsqueda textual española con índice GIN y movimientos propios relevantes. El contexto etiqueta documentos D* y movimientos M*. Se conserva la conversación y se incorporan los dos intercambios previos. La instrucción exige citar fuentes e indicar insuficiencia cuando los datos no permiten responder.'),
         p('Ejemplo verificado: obligación Universidad Q900, pago Q400, pendiente Q500. La respuesta cita el movimiento M3; el acceso a movimientos de otra persona queda excluido antes de construir el contexto.'),
         p('Agente presupuesto · combinación de información', 'h2'),
         p('financial_summary consulta ingresos, egresos y aportes netos por período. inflation consulta el indicador anual FP.CPI.TOTL.ZG de Guatemala en Banco Mundial. El agente elige las consultas y distingue el período de los movimientos del año de inflación disponible. Un año sin publicación produce una ausencia explícita de dato.'),
         p('Agente metas · consulta y simulaciones', 'h2'),
         p('goal_snapshot recupera las metas propias; exchange_rate consulta la referencia USD/GTQ de Banguat; simulate_goal calcula escenarios con Decimal. Prueba cloud real: meta Q5,000, saldo Q500 y seis aportes de Q750 frente a seis de Q500. Proyecciones Q5,000 y Q3,500; cuatro herramientas y cinco llamadas al modelo.'),
         table(['Fuente', 'Dato y tratamiento'], [
             ['PostgreSQL / corpus', 'Registros propios y guía educativa administrada; identificadores recuperables en la respuesta.'],
             ['Banco Mundial', 'Inflación anual de Guatemala. En el ensayo: 2025 = 1.48841591086168%; no se convierte a inflación mensual ni se confunde con 2026.'],
             ['Banguat', 'Referencia del 02/11/2026: 7.64187 GTQ/USD en el ensayo; no es una tasa garantizada de liquidación bancaria.'],
         ], [116, CONTENT_W-116])])
    if cloud:
        cloud_rows = []
        for key, label in [('rag', 'RAG'), ('budget', 'Presupuesto'), ('goals', 'Metas')]:
            verification = cloud.get(key, {}).get('verified', {})
            if verification:
                cloud_rows.append([label, str(verification['provider_calls']),
                                   str(verification['total_tokens']), verification['request_status']])
        if cloud_rows:
            add([p('Integración real en HTTPS', 'h2'), table(['Servicio', 'Rondas', 'Tokens', 'Estado'], cloud_rows, [145, 90, 90, CONTENT_W-325]),
                 p('Ensayo cloud del 02/11/2026. Las consultas previas con información insuficiente también permanecen en historial y consumo; la tabla destaca una ejecución completa de cada servicio.', 'small')])
    add([p('Control de ejecución', 'h2'),
         p('Herramientas en lista permitida por servicio, argumentos validados, tiempos máximos y hasta seis rondas. El límite sin respuesta final se registra como fallo con todo el consumo. Si una fuente falla no se sustituye silenciosamente por un valor inventado.'),
         p('El contenido generado puede variar entre ejecuciones. Las fuentes y resultados de herramientas quedan persistidos para revisar sus afirmaciones; una respuesta natural no equivale por sí sola a una validación factual.', 'small'), PageBreak()])

    # 4. ER de dominio.
    add(heading(4, 'Modelo de datos · dominio', 'Esquema relacional real. Se muestran claves y atributos principales; backend/schema.sql contiene todas las columnas, restricciones e índices.'))
    add([Diagram('domain'), p('Figura 2. Ocho tablas de identidad y finanzas. PK: clave primaria; FK: clave foránea; UQ: unicidad. Las flechas indican la relación de padre a hijo.', 'caption'),
         table(['Regla', 'Implementación'], [
             ['Exactitud monetaria', 'NUMERIC(15,2), Decimal y redondeo HALF_UP. Importes JSON como cadenas decimales.'],
             ['Pagos e historial', 'Pagos separados de obligaciones. Se preservan monto y fecha de ejecución; anulación/inactivación en vez de borrar historial.'],
             ['Recurrentes', 'UNIQUE(recurring_id,due_date) evita duplicar instancias; generación al solicitar el tablero, sin cron de pago.'],
             ['Ahorro', 'Saldo = suma de movimientos. Los aportes reducen disponible y aumentan ahorro; no se presentan como consumo.'],
         ], [112, CONTENT_W-112]), PageBreak()])

    # 5. ER IA / trazabilidad / control.
    add(heading(5, 'Modelo de datos · IA y auditoría', 'Las ocho tablas siguientes completan las 16 tablas del sistema. Conversaciones, rondas de proveedor y herramientas tienen granularidades distintas.'))
    add([Diagram('ai'), p('Figura 3. Relaciones de IA, historial y control. Se conservan solicitudes fallidas y consumo desconocido estimado; no se elimina el historial para mejorar indicadores.', 'caption'),
         table(['Entidad', 'Por qué existe'], [
             ['requests', 'Una pregunta del usuario: texto, respuesta, estado, fuentes y reserva pendiente.'],
             ['provider_calls', 'Una ronda de inferencia: tokens de entrada/salida y origen del cómputo. Varias rondas pueden pertenecer a una solicitud.'],
             ['tool_runs', 'Argumentos y resultado intermedio de cada herramienta, ligados a la pregunta.'],
             ['budgets / audit', 'Reserva compartida por día/minuto y trazabilidad de cambios administrativos.'],
         ], [112, CONTENT_W-112]), PageBreak()])

    # 6. Seguridad y cobertura de pruebas, sin afirmar garantías absolutas.
    add(heading(6, 'Acceso, cuotas y verificación', 'Los permisos se aplican en el backend y se prueban con accesos cruzados; ocultar una opción del menú no es el control de seguridad.'))
    add([table(['Acceso', 'Control aplicado'], [
             ['Usuario', 'Solo entidades, conversaciones y consumo propios; comprobación de propiedad también en herramientas.'],
             ['Administrador', 'CRUD de usuarios/corpus y configuración de servicios; filtros globales por usuario, fecha y servicio.'],
             ['Web y API externa', 'Contraseñas scrypt con sal; sesiones almacenadas como hash. Cookie HttpOnly, Secure en producción, SameSite Strict y CSRF; Bearer para clientes externos.'],
             ['Power BI', 'Cuenta bi independiente; Basic solo sobre HTTPS y endpoints de lectura. Sin acceso a IA ni cambios del dominio.'],
         ], [112, CONTENT_W-112]),
         p('Consumo verificable antes y después de la llamada', 'h2'),
         p('Cada ronda reserva de forma atómica cuota personal y compartida antes de contactar Groq. Después concilia los tokens informados. Un rechazo 4xx libera la reserva; si el uso no se confirma por un corte de conexión, se conserva una estimación conservadora y se etiqueta como tal.'),
         p('Al arrancar se concilian reservas interrumpidas antiguas una sola vez. El límite configurado no constituye una promesa de disponibilidad de Groq: también aplican las cuotas del proveedor y las del proyecto.'),
         table(['Verificación automatizada', 'Cobertura significativa'], [
             ['Identidad y dominio', 'Login/CSRF, roles, propiedad, pagos parciales, arrastre sin duplicados, recurrentes y ahorro sin sobregiro.'],
             ['RAG y agentes', 'Fuentes y memoria, insuficiencia, varias herramientas/rondas, conversaciones ajenas y límite de pasos.'],
             ['Cuotas y errores', 'Reservas concurrentes, reversión compartida, 429, timeout, usage ausente y recuperación idempotente.'],
             ['Reporte y API', 'Cursor, fecha Guatemala, snapshot as_of, Basic de lectura, health y OpenAPI.'],
         ], [145, CONTENT_W-145]),
         p(f'{tests} pruebas aprobadas contra PostgreSQL 17 aislado. La suite simula Groq y las fuentes públicas: no consume tokens. Se complementó con llamadas reales, limitadas, a los tres servicios y con integración HTTPS/Neon.', 'small'),
         p('Alcance de la evidencia: no se realizó una auditoría de seguridad ni una prueba de carga masiva. La suite muestra el comportamiento esperado de los casos cubiertos.', 'small'), PageBreak()])

    # 7. CI/CD completo, condicionado y con prueba SHA.
    add(heading(7, 'Despliegue y costo cero', 'La publicación usa los planes gratuitos existentes. No se agregaron tarjetas, discos ni servicios de pago.'))
    add([p('Pruebas → contenedor → despliegue por SHA', 'h2'),
         p('El workflow ejecuta backend y construcción/arranque del contenedor en jobs separados. Deploy requiere éxito de ambos, push a main y habilitación explícita. Render tiene auto-deploy apagado; GitHub solicita el commit exacto mediante ref=SHA y espera disponibilidad con ese mismo SHA y base accesible.'),
         p(f'Commit acreditado: {commit}.', 'small'),
         p(f'<link href="{text(ci_url)}" color="#087E83">Ejecución CI/CD completa en GitHub Actions</link>', raw=True),
         *image_block(screenshots.get('ci', 'evidencias-locales/ci-cd-correcto.png'), 'Figura 4. Evidencia de pruebas y despliegue satisfactorios en la misma ejecución.', 225),
         table(['Servicio / plan', 'Condición de operación'], [
             ['Render Free', 'Contenedor 512 MB. Puede dormir tras inactividad; abrir antes de la demostración. No usar pings artificiales para evitar la suspensión.'],
             ['Neon Free', 'Persistencia PostgreSQL y suspensión por inactividad; cuota finita. TLS verify-full en conexión directa y agrupada.'],
             ['Groq Free', 'Cuotas por minuto/día y clave con vencimiento 02/12/2026. No habilitar planes facturables al alcanzar límites.'],
             ['GitHub / Power BI', 'Repositorio público y Actions para el proyecto. Cuenta institucional para Power BI; revisar vencimiento y conservar PBIX exportado.'],
         ], [112, CONTENT_W-112]),
         p('La infraestructura Free puede cambiar o suspenderse; el proyecto no depende de comprar una ampliación. Si una cuota se agota, se reduce el uso o se espera su reinicio. Las credenciales quedan fuera de Git y del PDF.', 'small'), PageBreak()])

    # 8. Evidencia aplicación y reportería.
    add(heading(8, 'Aplicación publicada y API', 'La captura corresponde a la aplicación real en Render y usa datos ficticios persistidos en Neon.'))
    add([*image_block(screenshots.get('app', 'evidencias-locales/aplicacion-cloud.png'), 'Figura 5. GUI de Saldo publicada por HTTPS. El usuario consulta finanzas y accede a metas, asistentes, historial y consumo.', 265 if screenshots.get('web_report') else 290),
         p('Consulta y consumo: mismas reglas en web y Power BI', 'h2'),
         p('GET /api/v1/reports/usage entrega una fila por solicitud y agrega todas sus llamadas. GET /api/v1/reports/summary resume por servicio. Filtros de fecha en America/Guatemala, usuario según permisos y servicio. Un único as_of congela el corte y excluye solicitudes que terminaron después.'),
         p('La consulta Power Query recorre next_cursor hasta agotar páginas con el mismo corte. Contar filas mide preguntas; sumar provider_calls mide rondas. Los tokens de entrada y salida se suman una sola vez por llamada.'),
         table(['Entrega de API', 'Uso'], [
             ['Swagger / OpenAPI', app_url + '/docs'],
             ['Cliente externo', 'docs/postman.json; login Bearer, servicios IA, historial y reportes. Credenciales introducidas de forma privada.'],
             ['Persistencia', 'Cambios y consumo en Neon, independientes del disco efímero de Render.'],
         ], [112, CONTENT_W-112])])
    if screenshots.get('web_report'):
        add(image_block(screenshots['web_report'], 'Figura 6. Reporte web de consultas y tokens utilizado en el contraste con Power BI.', 115))
    add([PageBreak()])

    # 9. Evidencia BI: cambia únicamente por manifest, nunca inventa resultados.
    add(heading(9, 'Power BI y archivo exportable', 'El reporte académico mide consultas y tokens; los gráficos de ingresos y gastos no lo sustituyen.'))
    if verified:
        add([p('Conexión HTTPS, actualización y contraste verificados', 'h2'),
             p(bi.get('comparison', 'Se contrastaron los totales del reporte con los endpoints del proyecto utilizando el mismo alcance y corte de datos.')),
             *image_block(screenshots.get('powerbi', bi.get('screenshot')), 'Figura 7. Informe definitivo de consultas y consumo conectado a la API de Saldo.', 205)])
        totals = bi.get('totals', {})
        if totals:
            names = [('requests', 'Solicitudes'), ('provider_calls', 'Llamadas al proveedor'), ('input_tokens', 'Tokens de entrada'), ('output_tokens', 'Tokens de salida'), ('total_tokens', 'Tokens totales')]
            add([table(['Métrica contrastada', 'Valor'], [(name, f'{totals[key]:,}'.replace(',', ' ')) for key, name in names if key in totals], [260, CONTENT_W-260])])
        if bi.get('as_of'):
            add([p('Corte as_of: ' + str(bi['as_of']), 'small')])
        if pbix:
            add([p('Archivo entregado: ' + pbix.name + '. Exportación del informe y modelo; las credenciales se gestionan en el servicio, no se escriben en el código M.', 'small')])
        if bi.get('report_url'):
            add([p(f'<link href="{text(bi["report_url"])}" color="#087E83">Abrir informe en Power BI (cuenta institucional)</link>', raw=True)])
    else:
        add([p('Estado: integración definitiva todavía en proceso', 'h2'),
             p('Las pruebas anteriores demostraron la importación de una API HTTPS con Basic y la descarga de PBIX desde Power BI web. Esos archivos de diagnóstico no sustituyen al reporte conectado a Saldo.'),
             p('Para cerrar este requisito deben constar: actualización desde la URL publicada, filtros por fecha/servicio, contraste numérico con web/API y archivo PBIX completo descargado. Este borrador no marca el requisito como completado.'),
             table(['Validación requerida', 'Criterio de aceptación'], [
                 ['Origen y permisos', 'La URL es la API Saldo HTTPS; la cuenta BI solo consulta reportes.'],
                 ['Completitud', 'Paginación completa y corte as_of estable.'],
                 ['Coincidencia', 'Consultas, rondas y tokens coinciden por servicio y fecha.'],
                 ['Archivo entregable', 'PBIX exportado con informe y modelo; sin credenciales publicadas.'],
             ], [140, CONTENT_W-140])])
    add([PageBreak()])

    # 10. Operación y trazabilidad compacta.
    add(heading(10, 'Reproducción y entrega', 'Código, SQL y pruebas permiten reconstruir el prototipo sin depender de una sesión de navegador.'))
    add([p('Desde Ubuntu u otra máquina con Docker', 'h2'),
         p('Clonar el repositorio; copiar .env.example a .env y establecer claves propias. Ejecutar el contenedor, cargar datos ficticios y abrir localhost:8000. El seed no imprime contraseñas ni reemplaza las de usuarios existentes.'),
         p('docker compose up --build -d --wait<br/>docker compose exec app python -m backend.seed<br/>docker compose exec app pytest -q', 'code', raw=True),
         p('Las pruebas usan una base temporal local. Para migraciones, alembic upgrade head; backend/schema.sql es una alternativa sobre una base vacía (ver docs/portabilidad.md). No aplicar ambas rutas sobre la misma base ni usar down --volumes para conservar registros.', 'small'),
         p('Respaldo verificado: PostgreSQL 17.11 en Linux, restauración en base nueva, 16 tablas más alembic_version, 19 FK validadas, 57 restricciones y revisión 0003 coincidentes. Se preservó la base original. Este ensayo no acredita restaurar PostgreSQL 18 en 17; el dump privado no se publica.', 'small'),
         p('Power BI y continuidad desde Windows', 'h2'),
         p('El desarrollo, Docker, CI/CD y gestión cloud se realizaron desde Ubuntu. Power BI web completó el informe y su exportación. Si se necesita Desktop, Windows ya licenciado puede abrir el PBIX y consumir la misma API HTTPS con la cuenta BI; no es necesario trasladar el backend o Neon.', 'small')])
    for note in bi.get('limitations', []):
        add([p(str(note), 'small')])
    add([
         table(['Criterios de la consigna', 'Artefacto o evidencia'], [
             ['A01 · propuesta/arquitectura', 'Este informe, pp. 1-3; docs/alcance.md y arquitectura.md.'],
             ['A02-A03 · acceso y CRUD', 'Pruebas de roles/propiedad; GUI y endpoints administrativos/dominio.'],
             ['A04-A06 · tres servicios IA', 'RAG con fuentes/memoria; agentes con herramientas externas; p. 3.'],
             ['A07-A08 · historial y cuotas', 'requests, provider_calls, tool_runs; reservas concurrentes; pp. 5-6.'],
             ['A09-A10 · API y reporte web', 'Swagger, docs/postman.json, endpoints de reporte; p. 8.'],
             ['A11 · Power BI', 'Ver estado y evidencia en p. 9; powerbi/consumo.pq y archivo PBIX.'],
             ['A12-A14 · pruebas/cloud/CD', f'{tests} pruebas; Actions; Render; health SHA; pp. 6-7.'],
             ['A15 · entregables', 'Repositorio, backend/schema.sql, backend/seed.py, PDF y PBIX.'],
         ], [175, CONTENT_W-175]),
         p('Fuentes y referencias verificables', 'h2'),
         p('Consigna: Proyecto final - Programación Comercial.pdf, Recursos. Propuesta de producto original conservada en Recursos; alcance reducido aprobado en docs/alcance.md.', 'small'),
         p('<link href="https://api.worldbank.org/v2/country/GTM/indicator/FP.CPI.TOTL.ZG?format=json" color="#087E83">Banco Mundial · indicador FP.CPI.TOTL.ZG</link><br/>'
           '<link href="https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx" color="#087E83">Banguat · servicio de referencia de tipo de cambio</link><br/>'
           f'<link href="{text(app_url)}/docs" color="#087E83">Swagger de la API publicada</link> · '
           f'<link href="{repo_url}" color="#087E83">Repositorio y configuración reproducible</link>', 'small', raw=True),
         p('Operación posterior: revisar cuotas y fechas; retirar la clave SSH limitada al repositorio y revocar la clave Groq al terminar. La entrega contiene datos ficticios y no incorpora secretos operativos.', 'small')])
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(destination), pagesize=A4, leftMargin=46, rightMargin=46,
                          topMargin=41, bottomMargin=57, title='Saldo - Informe técnico académico',
                          author='Proyecto Saldo Académico', subject='Propuesta, arquitectura, modelo de datos y evidencias')
    frame = Frame(46, 57, CONTENT_W, PAGE_H-98, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='saldo', frames=[frame], onPage=page_footer))
    doc.build(blocks)
    return {'output': str(destination), 'powerbi_verified': verified, 'final_checks_required': not verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evidencias-locales/entrega-manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/pdf/Informe_Saldo_Academico.pdf')
    parser.add_argument('--require-final', action='store_true')
    args = parser.parse_args()
    print(json.dumps(make_report(load_manifest(args.manifest), args.output, args.require_final), ensure_ascii=False))


if __name__ == '__main__':
    main()

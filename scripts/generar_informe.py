#!/usr/bin/env python3
"""Informe académico reproducible. No lee .env ni contacta servicios externos.

Uso: python scripts/generar_informe.py [--manifest ruta.json] [--output ruta.pdf]
Depende únicamente de reportlab. La evidencia y su manifest son locales, no secretos.
Para entrega usar --require-final: exige manifest fechado, release, pruebas,
Power BI, PBIX y capturas comprobados. No reutiliza evidencia histórica por defecto.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from datetime import date
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
    def __init__(self, kind, model="openai/gpt-oss-120b"):
        super().__init__()
        self.kind = kind
        self.model = model
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
            box(386, 133, 117, 56, 'Groq Free', [self.model.split('/')[-1], 'Solo desde backend'])
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
            box(0, 341, 154, 74, 'services', ['PK id: rag / budget / goals', 'name · enabled · deleted_at', 'model · max_output · max_rounds'])
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
    canvas.drawString(46, 29, f'Saldo · Programación Comercial · {doc.review_date} · Datos ficticios')
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
    review_date = manifest.get('date', date.today().isoformat())
    date.fromisoformat(review_date)
    app_url = manifest.get('app_url', 'https://saldo-academico.onrender.com').rstrip('/')
    repo_url = manifest.get('repo_url', 'https://github.com/mariofrodm/saldo-academico')
    ci_url = manifest.get('ci_url', repo_url + '/actions')
    commit = manifest.get('commit', '')
    tests = manifest.get('tests_passed')
    tests_label = str(tests) if tests is not None else 'Cantidad pendiente de acreditar'
    model = manifest.get('model', 'openai/gpt-oss-120b')
    frontend_tests = manifest.get('frontend_tests')
    acceptance_checks = manifest.get('acceptance_checks')
    subtests = manifest.get('backend_subtests')
    release = manifest.get('release', {})
    released = release.get('status') == 'verified' and release.get('commit') == commit and bool(commit)
    bi = manifest.get('powerbi', {})
    verified = bi.get('status') in ('verified', 'complete', 'completado', 'verificado')
    pbix = resolve(bi.get('pbix_path'))
    screenshots = manifest.get('screenshots', {})
    captions = manifest.get('captions', {})
    if require_final:
        required = ('date', 'commit', 'ci_url', 'tests_passed', 'model')
        if any(not manifest.get(key) for key in required):
            raise ValueError('Falta fecha, commit, CI, pruebas o modelo explícitos para la entrega final.')
        if not re.fullmatch(r'[a-f0-9]{40}', commit) or not released:
            raise ValueError('La entrega final requiere release verificado del mismo SHA completo.')
        if not verified or not pbix or not pbix.is_file() or not bi.get('refresh_at') or not bi.get('totals'):
            raise ValueError('La entrega final requiere refresh, totales, verificación BI y PBIX existente.')
        for key in ('app', 'ci', 'powerbi', 'web_report'):
            path = resolve(screenshots.get(key))
            if not path or not path.is_file():
                raise ValueError(f'Falta captura final verificable: {key}.')
    cloud_path = resolve(manifest.get('cloud_evidence'))
    cloud = load_manifest(cloud_path) if cloud_path and cloud_path.is_file() else {}
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
             ['Exclusiones aprobadas', 'Tarjetas, FIFO, amortización contractual, multidivisa operativa, banca real y fondos compartidos. Las deudas sí pueden registrarse manualmente.'],
             ['Presupuesto', 'USD 0; capas Free, sin tarjetas ni activaciones de pago.'],
         ], [143, CONTENT_W-143]),
         Spacer(1, 10), p('Estado de esta revisión', 'h2'),
         p((f'Publicación acreditada del commit {commit[:7]}. ' if released else 'Borrador: publicación de esta revisión todavía no acreditada. ') +
           f'Pruebas backend: {tests_label}. ' +
           ('Power BI verificado; el archivo PBIX forma parte de esta entrega.' if verified else
            'Power BI pendiente de acreditar para esta revisión.')),
         p(manifest.get('status_note', ''), 'small'),
         p(f'Corte del informe: {review_date}. Fecha de entrega indicada en la consigna: 10 de noviembre. Los registros de demostración son ficticios.', 'small'),
         p(f'<b>Aplicación:</b> <link href="{text(app_url)}" color="#087E83">{text(app_url)}</link><br/>'
           f'<b>Repositorio:</b> <link href="{repo_url}" color="#087E83">{repo_url}</link>', raw=True),
         PageBreak()])

    # 2. Arquitectura y recorrido GUI / consumidor externo.
    add(heading(2, 'Arquitectura y stack', 'Un solo contenedor publica React y FastAPI en HTTPS. PostgreSQL conserva el estado; Render no requiere disco persistente.'))
    add([Diagram('architecture', model), p('Figura 1. Recorrido real desde GUI, cliente externo y Power BI. Las claves de Groq y Neon permanecen en el servidor.', 'caption'),
         table(['Componente', 'Tecnología y responsabilidad'], [
             ['Interfaz', 'React 19.3.1, TypeScript 7.0.2 y Vite 8.3.5; compilación estática.'],
             ['API', 'Python 3.12, FastAPI 0.162.0, Pydantic, Uvicorn y psycopg 3.3.6; SQL parametrizado.'],
             ['Persistencia', 'PostgreSQL 18.6 en Neon Free; PostgreSQL 17 en local/CI; migraciones Alembic.'],
             ['Inferencia', f'Groq Free, {model}; herramientas autorizadas y límites por ronda.'],
             ['Publicación', 'Docker multietapa, usuario sin privilegios; Render Free 512 MB; GitHub Actions.'],
             ['Analítica', 'Power BI web con importación HTTPS Basic; PBIX exportable y ruta Desktop si fuese necesaria.'],
         ], [112, CONTENT_W-112]),
         p('Fabric no es una dependencia del backend. El RAG usa recuperación textual nativa de PostgreSQL; no requiere servicio vectorial ni embeddings de pago.', 'small'), PageBreak()])

    # 3. Tres servicios distintos y fuentes reales.
    add(heading(3, 'Servicios de IA y fuentes', 'El modelo decide herramientas y continúa con sus resultados. Los cálculos monetarios y las consultas autorizadas los ejecuta el backend.'))
    add([p('RAG · respuesta sobre información recuperada', 'h2'),
         p('La pregunta recupera corpus activo mediante búsqueda textual española de PostgreSQL y movimientos propios relevantes. Las guías Markdown se fragmentan e indexan explícitamente; no hay embeddings ni entrenamiento propio. Se conservan hasta seis intercambios completos y referencias verificadas, dentro de un presupuesto acotado. El chat responde en lenguaje natural; fuentes y herramientas se revisan en Historial. Cuando falta información debe reconocerla.'),
         p('Ejemplo de cálculo: una obligación de Q900 con un abono de Q400 deja Q500 pendientes. La base conserva obligación y pago por separado; el acceso a movimientos ajenos se excluye antes de construir el contexto. La documentación educativa es contexto, no una autorización de acceso.'),
         p('Agente presupuesto · combinación de información', 'h2'),
         p('budget_external_review reúne flujo propio e inflación anual de Guatemala (FP.CPI.TOTL.ZG, Banco Mundial). El modelo elige sus argumentos y el backend ejecuta pasos de lectura y consulta externa; una segunda inferencia explica. El período financiero y el año externo se validan por separado. Si el dato no está publicado se informa; no se inventa inflación mensual.'),
         p('Agente metas · consulta y simulaciones', 'h2'),
         p('goal_external_scenarios consulta la meta propia elegida, calcula dos escenarios con Decimal y obtiene Banguat si se pidió. El modelo selecciona la herramienta y los argumentos; el backend realiza esos pasos secuenciales y la segunda inferencia explica. No modifica saldos ni promete asequibilidad. La referencia cambiaria no es una tasa bancaria garantizada.'),
         table(['Fuente', 'Dato y tratamiento'], [
             ['PostgreSQL / corpus', 'Registros propios y guía educativa administrada; fuentes y resultados recuperables desde Historial.'],
             ['Banco Mundial', 'Inflación anual de Guatemala, con año, disponibilidad y procedencia. No convertirla a inflación mensual ni usarla como predicción.'],
             ['Banguat', 'Referencia diaria USD/GTQ con fecha devuelta por la fuente. No es una tasa garantizada de liquidación bancaria.'],
         ], [116, CONTENT_W-116])])
    cloud_rows = []
    if cloud:
        for key, label in [('rag', 'RAG'), ('budget', 'Presupuesto'), ('goals', 'Metas')]:
            verification = cloud.get(key, {}).get('verified', {})
            if verification:
                cloud_rows.append([label, str(verification.get('provider_calls', '')),
                                   str(verification.get('total_tokens', '')), verification.get('request_status', '')])
    add([p('Control de ejecución', 'h2'),
         p('Herramientas de lectura en lista permitida por servicio, argumentos validados, tiempos máximos y hasta seis rondas. El recorrido general carga la guía 00 versionada. Los dos recorridos externos usan external_system específico y compacto, con referencias verificadas y hechos recién consultados, sin enviar la guía completa ni prosa vieja. Los esquemas se seleccionan según la petición. Algunas consultas sencillas usan respuestas calculadas sin Groq. La memoria y los detalles opcionales se compactan preservando pregunta, fechas, reglas y totales. Un límite sin resultado final queda registrado; no se inventa una respuesta de proveedor.'),
         p('El contenido generado puede variar entre ejecuciones. Las fuentes y resultados de herramientas quedan persistidos para revisar sus afirmaciones; una respuesta natural no equivale por sí sola a una validación factual.', 'small'), PageBreak()])

    # 4. ER de dominio.
    add(heading(4, 'Modelo de datos · dominio', 'Esquema relacional real. Se muestran claves y atributos principales; backend/schema.sql contiene todas las columnas, restricciones e índices.'))
    add([Diagram('domain'), p('Figura 2. Ocho tablas de identidad y finanzas. PK: clave primaria; FK: clave foránea; UQ: unicidad. Las flechas indican la relación de padre a hijo.', 'caption'),
         table(['Regla', 'Implementación'], [
             ['Exactitud monetaria', 'NUMERIC(15,2), Decimal y redondeo HALF_UP. Importes JSON como cadenas decimales.'],
             ['Pagos e historial', 'Pagos separados de obligaciones. Se preservan monto y fecha; anulación/inactivación para registros con historial. El borrado de meta y sus movimientos es explícito, transaccional y auditado.'],
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
             ['Administrador', 'CRUD de usuarios/corpus y configuraciones de los tres servicios; baja lógica de cuentas/servicios, historial conservado y filtros globales por usuario, fecha y servicio.'],
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
         p(f'Pruebas backend acreditadas por este manifest: {tests_label}. La suite usa PostgreSQL 17 aislado y simula Groq/fuentes públicas: no consume tokens. La aceptación real se documenta por separado en el entorno publicado.', 'small'),
         p('Comprobaciones adicionales del manifest: ' + (', '.join(f'{label}: {value}' for label, value in [('subpruebas backend', subtests), ('frontend', frontend_tests), ('aceptación API', acceptance_checks)] if value is not None) or 'No consignadas') + '.', 'small'),
         p('Alcance de la evidencia: no se realizó una auditoría de seguridad ni una prueba de carga masiva. La suite muestra el comportamiento esperado de los casos cubiertos.', 'small'), PageBreak()])

    # 7. CI/CD completo, condicionado y con prueba SHA.
    add(heading(7, 'Despliegue y costo cero', 'La publicación usa los planes gratuitos existentes. No se agregaron tarjetas, discos ni servicios de pago.'))
    add([p('Pruebas → contenedor → despliegue por SHA', 'h2'),
         p('El workflow ejecuta backend y construcción/arranque del contenedor en jobs separados. Deploy requiere éxito de ambos, push a main y habilitación explícita. Render tiene auto-deploy apagado; GitHub solicita el commit exacto mediante ref=SHA y espera disponibilidad con ese mismo SHA y base accesible.'),
         p(f'Commit de implementación: {commit or "Pendiente de acreditar"}. Estado de publicación: {"verificado" if released else "pendiente"}.', 'small'),
         p(f'<link href="{text(ci_url)}" color="#087E83">Ejecución CI/CD completa en GitHub Actions</link>', raw=True),
         *image_block(screenshots.get('ci'), captions.get('ci', 'Figura 4. Evidencia de pruebas y despliegue satisfactorios en la misma ejecución.'), 225),
         table(['Servicio / plan', 'Condición de operación'], [
             ['Render Free', 'Contenedor 512 MB. Puede dormir tras inactividad; abrir antes de la demostración. No usar pings artificiales para evitar la suspensión.'],
             ['Neon Free', 'Persistencia PostgreSQL y suspensión por inactividad; cuota finita. TLS verify-full en conexión directa y agrupada.'],
             ['Groq Free', 'Cuotas por minuto/día y clave con vencimiento 02/12/2026. No habilitar planes facturables al alcanzar límites.'],
             ['GitHub / Power BI', 'Repositorio público y Actions para el proyecto. Cuenta institucional para Power BI; revisar vencimiento y conservar PBIX exportado.'],
         ], [112, CONTENT_W-112]),
         p('La infraestructura Free puede cambiar o suspenderse; el proyecto no depende de comprar una ampliación. Si una cuota se agota, se reduce el uso o se espera su reinicio. Las credenciales quedan fuera de Git y del PDF.', 'small'), PageBreak()])

    # 8. Evidencia aplicación y reportería.
    add(heading(8, 'Aplicación publicada y API', 'La evidencia corresponde al entorno declarado en el manifest; no se reutilizan capturas locales como publicación.'))
    add([*image_block(screenshots.get('app'), captions.get('app', 'Figura 5. GUI de Saldo publicada por HTTPS. El usuario consulta finanzas y accede a metas, asistentes, historial y consumo.'), 265 if screenshots.get('web_report') else 290),
         p('Consulta y consumo: mismas reglas en web y Power BI', 'h2'),
         p('GET /api/v1/reports/usage entrega una fila por solicitud y agrega todas sus llamadas. GET /api/v1/reports/summary resume por servicio. Filtros de fecha en America/Guatemala, usuario según permisos y servicio. Un único as_of congela el corte y excluye solicitudes que terminaron después.'),
         p('La consulta Power Query recorre next_cursor hasta agotar páginas con el mismo corte. Contar filas mide preguntas; sumar provider_calls mide rondas. Los tokens de entrada y salida se suman una sola vez por llamada.'),
         table(['Entrega de API', 'Uso'], [
             ['Swagger / OpenAPI', app_url + '/docs'],
             ['Cliente externo', 'docs/postman.json; login Bearer, servicios IA, historial y reportes. Credenciales introducidas de forma privada.'],
             ['Persistencia', 'Cambios y consumo en Neon, independientes del disco efímero de Render.'],
         ], [112, CONTENT_W-112])])
    if screenshots.get('web_report') and screenshots.get('web_report') != screenshots.get('app'):
        add(image_block(screenshots['web_report'], captions.get('web_report', 'Figura 6. Reporte web de consultas y tokens utilizado en el contraste con Power BI.'), 115))
    add([PageBreak()])

    # 9. Evidencia BI: cambia únicamente por manifest, nunca inventa resultados.
    add(heading(9, 'Power BI y archivo exportable', 'El reporte académico mide consultas y tokens; los gráficos de ingresos y gastos no lo sustituyen.'))
    if verified:
        add([p('Conexión HTTPS, actualización y contraste verificados', 'h2'),
             p(bi.get('comparison', 'Se contrastaron los totales del reporte con los endpoints del proyecto utilizando el mismo alcance y corte de datos.')),
             *image_block(screenshots.get('powerbi', bi.get('screenshot')), captions.get('powerbi', 'Figura 7. Informe definitivo de consultas y consumo conectado a la API de Saldo.'), 205)])
        totals = bi.get('totals', {})
        if totals:
            names = [('requests', 'Solicitudes'), ('provider_calls', 'Llamadas al proveedor'), ('input_tokens', 'Tokens de entrada'), ('output_tokens', 'Tokens de salida'), ('total_tokens', 'Tokens totales')]
            add([table(['Métrica contrastada', 'Valor'], [(name, f'{totals[key]:,}'.replace(',', ' ')) for key, name in names if key in totals], [260, CONTENT_W-260])])
        if bi.get('as_of'):
            add([p('Corte as_of: ' + str(bi['as_of']), 'small')])
        if bi.get('refresh_at'):
            add([p('Actualización del modelo: ' + str(bi['refresh_at']), 'small')])
        if pbix:
            add([p('Archivo entregado: ' + pbix.name + '. Informe y modelo importado. La contraseña se configura fuera de M. Un PBIX descargado es una copia fechada: no se renueva al refrescar la vista web.', 'small')])
        if bi.get('report_url'):
            add([p(f'<link href="{text(bi["report_url"])}" color="#087E83">Abrir informe en Power BI (cuenta institucional)</link>', raw=True)])
    else:
        add([p('Estado: integración definitiva todavía en proceso', 'h2'),
             p('La integración anterior ya consumió la API Saldo por HTTPS con Basic y permitió descargar un PBIX completo desde la web. Ese archivo acredita su corte histórico; falta actualizar y contrastar la revisión nueva antes de considerarlo definitivo.'),
             p('Para cerrar este requisito deben constar: actualización desde la URL publicada, filtros por fecha/servicio, contraste numérico con web/API y archivo PBIX completo descargado. Este borrador no marca el requisito como completado.'),
             table(['Validación requerida', 'Criterio de aceptación'], [
                 ['Origen y permisos', 'La URL es la API Saldo HTTPS; la cuenta BI solo consulta reportes.'],
                 ['Completitud', 'Paginación completa y corte as_of estable.'],
                 ['Coincidencia', 'Consultas, rondas y tokens coinciden por servicio y fecha.'],
                 ['Archivo entregable', 'PBIX exportado con informe y modelo; sin credenciales publicadas.'],
             ], [140, CONTENT_W-140])])
        if screenshots.get('powerbi'):
            add([Spacer(1, 8)])
            add(image_block(screenshots['powerbi'], bi.get('draft_caption', 'Captura de diagnóstico anterior: no acredita el contraste final de esta revisión.'), 195))
    for note in bi.get('limitations', []):
        add([p(str(note), 'small')])
    add([PageBreak()])

    # 10. Operación y trazabilidad compacta.
    add(heading(10, 'Reproducción y entrega', 'Código, SQL y pruebas permiten reconstruir el prototipo sin depender de una sesión de navegador.'))
    add([p('Desde Ubuntu u otra máquina con Docker', 'h2'),
         p('Clonar el repositorio; copiar .env.example a .env y establecer contraseñas propias. Ejecutar el contenedor, seed, escenario local e indexación de guías y abrir localhost:8000. No se comparten secretos. El seed no imprime contraseñas ni reemplaza las de usuarios existentes.'),
         p('docker compose up --build -d --wait<br/>docker compose exec app python -m backend.seed<br/>docker compose exec app python -m backend.demo<br/>docker compose exec app python -m backend.knowledge<br/>docker compose exec app pytest -q', 'code', raw=True),
         p('Las pruebas usan una base temporal local. Para migraciones, alembic upgrade head; backend/schema.sql es una alternativa sobre una base vacía (ver docs/portabilidad.md). No aplicar ambas rutas sobre la misma base ni usar down --volumes para conservar registros.', 'small'),
         p(manifest.get('restore_summary', 'Recuperación: generar un respaldo privado y comprobarlo en una base nueva, preservando la original. Usar herramientas y destino compatibles con la versión de PostgreSQL. Las evidencias de restauración y revisión de esquema se registran por separado; no se asume que un dump 18 se restaure en 17.'), 'small'),
         p('Power BI y continuidad desde Windows', 'h2'),
         p('El desarrollo, Docker, CI/CD y gestión cloud se realizaron desde Ubuntu. Power BI web completó el informe y su exportación. Si se necesita Desktop, Windows ya licenciado puede abrir el PBIX y consumir la misma API HTTPS con la cuenta BI; no es necesario trasladar el backend o Neon.', 'small')])
    add([
         table(['Criterios de la consigna', 'Artefacto o evidencia'], [
             ['A01 · propuesta/arquitectura', 'Este informe; docs/alcance.md, arquitectura.md y como-funciona.md.'],
             ['A02-A03 · acceso y CRUD', 'Pruebas de roles/propiedad; GUI y endpoints administrativos/dominio.'],
             ['A04-A06 · tres servicios IA', 'RAG con fuentes/memoria; agentes con herramientas externas.'],
             ['A07-A08 · historial y cuotas', 'requests, provider_calls, tool_runs; reservas concurrentes.'],
             ['A09-A10 · API y reporte web', 'Swagger, docs/postman.json, endpoints de reporte.'],
             ['A11 · Power BI', 'Ver estado y evidencia en la sección Power BI; powerbi/consumo.pq y archivo PBIX.'],
             ['A12-A14 · pruebas/cloud/CD', f'{tests_label} pruebas backend; Actions; Render; health SHA.'],
             ['A15 · entregables', 'Repositorio, backend/schema.sql, backend/seed.py, PDF y PBIX.'],
         ], [175, CONTENT_W-175]),
         p('Fuentes y referencias verificables', 'h2'),
         p('Consigna: Proyecto final - Programación Comercial.pdf, Recursos. Propuesta de producto original conservada en Recursos; alcance reducido aprobado en docs/alcance.md.', 'small'),
         p('<link href="https://api.worldbank.org/v2/country/GTM/indicator/FP.CPI.TOTL.ZG?format=json" color="#087E83">Banco Mundial · indicador FP.CPI.TOTL.ZG</link><br/>'
           '<link href="https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx" color="#087E83">Banguat · servicio de referencia de tipo de cambio</link><br/>'
           f'<link href="{text(app_url)}/docs" color="#087E83">Swagger de la API publicada</link> · '
           f'<link href="{repo_url}" color="#087E83">Repositorio y configuración reproducible</link>', 'small', raw=True),
         p('Guía sencilla completa: docs/como-funciona.md. Recorrido de exposición: docs/guion-demostracion.md. Instalación y recuperación: README.md y docs/portabilidad.md. Operación posterior: revisar cuotas y fechas; retirar los accesos temporales al terminar. La entrega contiene datos ficticios y no incorpora secretos.', 'small')])
    if screenshots.get('local_finances'):
        add([PageBreak()])
        add(heading(11, 'Recorrido de los datos', 'El mismo backend valida registros, calcula hechos, coordina la IA y entrega el reporte.'))
        add([p('Del formulario al informe', 'h2'),
             p('React envía un registro autenticado; FastAPI valida propiedad, fecha y monto y PostgreSQL lo conserva. Al preguntar, la API recupera guías y hechos propios. Una consulta calculada responde sin modelo; una consulta abierta reserva cuota y usa Groq con herramientas permitidas. Respuesta, fuentes, pasos y tokens quedan en el historial. La API de reportes agrega ese consumo y Power BI importa una copia con corte estable.'),
             *image_block(screenshots['local_finances'], captions.get('local_finances', 'Figura 8. Escenario local ampliado de Ana: noviembre Q6.000 de ingresos, Q2.277 de pagos, Q1.275 de ahorro neto y Q2.448 de flujo. No es la base cloud ni el origen del Power BI publicado.'), 285),
             p('Dos instalaciones y un alcance explícito', 'h2'),
             p('El código puede ser el mismo en Ubuntu y Render, pero sus bases son independientes. Publicar no copia los registros locales. Cloud conserva la semilla financiera mientras la copia ampliada de Ana espera confirmación específica; su reporte Power BI sí incluye las consultas cloud contrastadas. El manual distingue preguntas y cifras de cada instalación.'),
             table(['Capa', 'Datos y acceso'], [
                 ['Finanzas', 'Obligaciones, pagos, metas y movimientos propios. Cálculos Decimal; sin operaciones bancarias.'],
                 ['Asesor', 'Guía general versionada, recuperación textual y herramientas de lectura. Flujos externos específicos con instrucciones compactas.'],
                 ['Historial y BI', 'Solicitudes, herramientas y llamadas persistidas; API HTTPS paginada y cuenta BI de lectura.'],
             ], [112, CONTENT_W-112])])
    if cloud_rows:
        add([PageBreak()])
        add(heading(12, 'Pruebas reales del asesor', 'Las cifras siguientes corresponden a ejecuciones concretas y no certifican todas las formulaciones posibles.'))
        add([table(['Servicio cloud', 'Llamadas', 'Tokens', 'Resultado observado'], cloud_rows, [110, 60, 60, CONTENT_W-230]),
             p(manifest.get('ai_validation_note', 'Los fallos y las consultas con información insuficiente también permanecen en historial y consumo. Los cálculos y las recomendaciones se revisan por separado.')),
             p('Fuentes externas y cálculos comprobados', 'h2'),
             p('Banco Mundial devolvió inflación anual Guatemala 2025 de 1,48841591086168 %. Banguat devolvió referencia 7,64243 GTQ/USD con fecha 8/11/2026. No se convirtieron en inflación mensual, rendimiento ni tasa bancaria garantizada.'),
             p('En cloud la meta parte de Q500: seis aportes de Q500 producen Q3.500 y seis de Q750 producen Q5.000. En el ensayo local final parte de Q550: los mismos escenarios producen Q3.550 y Q5.050. La diferencia procede de bases distintas, no de un cambio de fórmula.'),
             p('Qué protege la versión final', 'h2'),
             p('Las herramientas solo leen datos propios y hacen la aritmética. La guarda numérica contrasta importes y la barrera de capacidad evita presentar el flujo registrado como dinero libre para comprometer. Si falta calendario, mínimos o condiciones contractuales, se explican las ausencias. Una proyección no registra un pago ni demuestra asequibilidad.'),
             p('Límites de la aceptación', 'h2'),
             p('El candidato real de presupuesto y el ensayo anterior de metas motivaron correcciones de redacción y regresiones con los textos archivados. El ensayo de metas con instrucciones finales se repitió con IA real en local; no se ocultaron ni descontaron los consumos anteriores. Las fuentes y pasos quedan disponibles en Historial.'),
             p('Las pruebas automatizadas usan proveedores simulados; su éxito no promete disponibilidad externa permanente. La demostración debe revisar las cuotas y el entorno elegido antes de comenzar. La copia ampliada de Ana a la nube sigue separada y pendiente de confirmación.'),
             p('Evidencia detallada privada: cierre-20261108; guía pública de reproducción y aceptación en docs/. No se publican contraseñas, claves ni respaldos.', 'small')])
    destination.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(destination), pagesize=A4, leftMargin=46, rightMargin=46,
                          topMargin=41, bottomMargin=57, title='Saldo - Informe técnico académico',
                          author='Proyecto Saldo Académico', subject='Propuesta, arquitectura, modelo de datos y evidencias')
    doc.review_date = review_date
    frame = Frame(46, 57, CONTENT_W, PAGE_H-98, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id='saldo', frames=[frame], onPage=page_footer))
    doc.build(blocks)
    return {'output': str(destination), 'date': review_date, 'commit': commit, 'release_verified': released, 'powerbi_verified': verified, 'final_checks_required': not (verified and released)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'evidencias-locales/entrega-manifest.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'output/pdf/Informe_Saldo_Academico.pdf')
    parser.add_argument('--require-final', action='store_true')
    args = parser.parse_args()
    print(json.dumps(make_report(load_manifest(args.manifest), args.output, args.require_final), ensure_ascii=False))


if __name__ == '__main__':
    main()

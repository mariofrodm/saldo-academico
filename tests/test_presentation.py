from backend.presentation import natural_text
import pytest


def test_comparison_from_screenshot_is_readable_without_changing_values():
    text = 'En octubre pagaste **más en Alimentación (Q1\u202f000\u202f.00) que en Universidad (Q900.00)**.\nFuente: [SGASTOS] (spending_breakdown 2026-10-01–2026-10-31).'
    assert natural_text(text) == 'En octubre pagaste más en Alimentación (Q1,000.00) que en Universidad (Q900.00).'


def test_debt_table_becomes_readable_lines_without_internal_identifiers():
    text = '''**Deudas actuales (corte 2026-11-08)**
| ID | Título | Saldo pendiente (GTQ) | Vencimiento |
|----|--------|------------------------|-------------|
| 161 | Préstamo familiar | 550,00 | 2026-11-30 |
| 162 | Compra de computadora | 2\u202f050,00 | 2026-11-30 |

Total pendiente: **7900,00 GTQ**.
Fuente: [SDEUDA] (debt_snapshot).

### Cómo aplicar la **bola de nieve**
No conocemos las tasas ni los mínimos. No garantizo una fecha.'''
    result = natural_text(text)
    assert 'Préstamo familiar: saldo pendiente: Q550.00; vencimiento: 2026-11-30.' in result
    assert 'Compra de computadora: saldo pendiente: Q2,050.00' in result
    assert 'Q7,900.00' in result
    assert 'No conocemos las tasas ni los mínimos. No garantizo una fecha.' in result
    assert not any(mark in result for mark in ('|', '**', '###', 'Fuente:', 'SDEUDA', '161', '162'))


def test_plain_text_negations_dates_ranges_and_unrelated_brackets_are_preserved():
    text = 'No es tu saldo bancario. Del 2026-10-01 al 2026-10-31; entre 3 y 6 meses.\n\nNo conocemos el interés [pendiente de confirmar].'
    assert natural_text(text) == text


def test_notation_is_idempotent_and_does_not_invent_arithmetic():
    text = 'Aporte: Q500.00. Retiro: Q-50.00. No hay tasa confirmada. [SMETAS]'
    first = natural_text(text)
    assert 'Q500.00' in first and 'Q-50.00' in first
    assert '450' not in first
    assert natural_text(first) == first


@pytest.mark.parametrize(('text', 'expected'), [
    ('Q1 000 y 2 050,50 GTQ', 'Q1,000.00 y Q2,050.50'),
    ('Q1\u202f000\u202f.00', 'Q1,000.00'),
    ('Q-1 000,50 y -20 GTQ', 'Q-1,000.50 y Q-20.00'),
    ('Q1,234.56 y Q1.234,56', 'Q1,234.56 y Q1,234.56'),
    ('Monto Q100, no Q200.', 'Monto Q100.00, no Q200.00.'),
    ('1,025 Q mensuales; 741.67\u202fQ al mes.', 'Q1,025.00 mensuales; Q741.67 al mes.'),
])
def test_money_normalizes_only_valid_notation_without_rounding(text, expected):
    result = natural_text(text)
    assert result == expected
    assert natural_text(result) == result


@pytest.mark.parametrize('text', [
    'Q1 20', 'Q1.23.45', 'Q1,23.45', 'Q1,234.567,89',
    'Q1.234', 'Q123.4567', 'SKUQ100 ni ID123 GTQ',
])
def test_ambiguous_or_invalid_money_and_embedded_identifiers_are_not_rewritten(text):
    assert natural_text(text) == text


def test_plain_pipes_and_qualifications_cannot_be_discarded_as_metadata():
    text = '| No pagues sin confirmar los mínimos |\n\nReferencia: no es saldo bancario.\nFuente: salario Q6000.'
    result = natural_text(text)
    assert result == '| No pagues sin confirmar los mínimos |\n\nReferencia: no es saldo bancario.\nFuente: salario Q6,000.00.'


def test_warning_after_a_citation_remains_in_full():
    text = 'No pagues sin confirmar. Fuente: [SDEUDA] (debt_snapshot) No conocemos las tasas ni los mínimos.'
    result = natural_text(text)
    assert result == 'No pagues sin confirmar. No conocemos las tasas ni los mínimos.'
    assert natural_text('Fuente: [SDEUDA] y [SGASTOS].') == ''
    assert natural_text('**Fuente:** [SDEUDA] (debt_snapshot).') == ''


def test_unrelated_brackets_and_mathematical_operators_keep_their_meaning():
    text = 'La casilla [SI] y la nota [SIN INTERESES] permanecen.\n2 * 3 = 6 y 4 * 5 = 20.\n2 ** 3 ** 4.\n> Q500 no implica capacidad garantizada.'
    assert natural_text(text) == text.replace('Q500', 'Q500.00')
    assert natural_text('**No** es *seguro* ni __garantizado__.') == 'No es seguro ni garantizado.'


def test_table_does_not_drop_other_columns_with_the_same_value_as_its_title():
    text = '| Concepto | Acción | Importe (GTQ) |\n|---|---|---|\n| Revisar | Revisar | 25 |'
    assert natural_text(text) == 'Revisar: acción: Revisar; importe: Q25.00.'


def test_table_discards_internal_columns_but_keeps_empty_and_negative_facts():
    text = '| source_id | Meta | ¿Financiada? | Saldo (GTQ) |\n|---|---|---|---|\n| SG12 | Fondo | No | -50,00 |'
    result = natural_text(text)
    assert result == 'Fondo: ¿financiada?: No; saldo: Q-50.00.'
    assert 'SG12' not in result


def test_multiple_table_rows_become_separate_paragraphs():
    text = '| Categoría | Pagos (GTQ) |\n|---|---|\n| Vivienda | 1500 |\n| Salud | 250 |'
    assert natural_text(text) == 'Vivienda: pagos: Q1,500.00.\n\nSalud: pagos: Q250.00.'


@pytest.mark.parametrize('code,tool', [('SGASTOS', 'spending_breakdown'), ('SCOMPARA', 'compare_spending'), ('SG12', 'savings_plan'), ('SPLAN', 'planning_snapshot')])
def test_explicit_sources_with_bare_known_codes_are_not_shown(code, tool):
    assert natural_text(f'Revisé tus registros.\n\nFuente: {code} ({tool})') == 'Revisé tus registros.'
    assert natural_text(f'No pagues sin confirmar. Fuente: {code} ({tool}) No conocemos las tasas ni los mínimos.') == (
        'No pagues sin confirmar. No conocemos las tasas ni los mínimos.')
    # Exact known codes cannot consume parts of identifiers or unrelated words.
    assert natural_text(f'El identificador literal {code} permanece fuera de una anotación de fuente.') == (
        f'El identificador literal {code} permanece fuera de una anotación de fuente.')


def test_unrelated_bare_source_words_and_compare_tool_label_are_preserved():
    assert natural_text('Fuente: SI significa una confirmación, no una garantía.') == 'Fuente: SI significa una confirmación, no una garantía.'
    assert natural_text('Fuente: SGASTOS_EXTRA no confirma mínimos.') == 'Fuente: SGASTOS_EXTRA no confirma mínimos.'
    assert natural_text('compare_spending no calcula intereses.') == 'comparación de pagos por categoría no calcula intereses.'


def test_planning_source_is_metadata_but_unrelated_annotations_remain():
    assert natural_text('Revisé tus metas. [SPLAN]') == 'Revisé tus metas.'
    assert natural_text('planning_snapshot no modifica saldos.') == 'planificación de metas no modifica saldos.'
    assert natural_text('La nota [SPLAN_EXTRA] no es una fuente del sistema.') == 'La nota [SPLAN_EXTRA] no es una fuente del sistema.'


@pytest.mark.parametrize(('text', 'expected'), [
    ('- Revisa primero las fechas.\n- No omitas necesidades básicas.',
     'Revisa primero las fechas.\nNo omitas necesidades básicas.'),
    ('1. Revisa tus metas.\n2) Elige una prioridad.', 'Revisa tus metas.\nElige una prioridad.'),
    ('* Ámbitos distintos no se suman.\n+ Confirma el aporte.', 'Ámbitos distintos no se suman.\nConfirma el aporte.'),
    ('- Q100\n-100\n- 100\n- Q-100', '- Q100.00\n-100\n- 100\n- Q-100.00'),
    ('- GTQ100\n1. Q100\n2 * 3 = 6\n2 - 3 = -1', '- GTQ100\n1. Q100.00\n2 * 3 = 6\n2 - 3 = -1'),
    ('161. Préstamo familiar\n- ID 12\n12. ID 161\nSKU-100',
     '161. Préstamo familiar\n- ID 12\n12. ID 161\nSKU-100'),
])
def test_sentence_list_markers_are_removed_without_changing_amount_signs_or_identifiers(text, expected):
    result = natural_text(text)
    assert result == expected
    assert natural_text(result) == result

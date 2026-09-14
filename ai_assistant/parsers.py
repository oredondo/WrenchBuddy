import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


VALID_TASK_CODES = {
    'oil_change', 'chain_service', 'tire_check', 'brake_check',
    'coolant_change', 'spark_plugs', 'air_filter', 'itv',
}

KEYWORD_TO_TASK_CODE = {
    'aceite': 'oil_change',
    'filtro aceite': 'oil_change',
    'cambio de aceite': 'oil_change',
    'cadena': 'chain_service',
    'tensado cadena': 'chain_service',
    'limpieza cadena': 'chain_service',
    'neumático': 'tire_check',
    'neumatico': 'tire_check',
    'rueda': 'tire_check',
    'freno': 'brake_check',
    'frenos': 'brake_check',
    'pastillas de freno': 'brake_check',
    'disco de freno': 'brake_check',
    'refrigerante': 'coolant_change',
    'líquido refrigerante': 'coolant_change',
    'anticongelante': 'coolant_change',
    'bujía': 'spark_plugs',
    'bujias': 'spark_plugs',
    'bujías': 'spark_plugs',
    'filtro aire': 'air_filter',
    'filtro de aire': 'air_filter',
    'itv': 'itv',
    'inspección técnica': 'itv',
    'revisión técnica': 'itv',
}


@dataclass
class ParsedAnalysis:
    task_codes: list[str] = field(default_factory=list)
    date: Optional[date] = None
    km: Optional[int] = None
    cost: Optional[Decimal] = None
    notes_extra: str = ''


def parse_analysis_result(text: str) -> ParsedAnalysis:
    """Parse AI analysis result. Tries JSON first, then regex fallback."""
    result = _try_parse_json(text)
    if result is not None:
        return result
    return _parse_regex_fallback(text)


def _clean_json_text(text: str) -> str:
    """Remove markdown code fences from JSON text."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _try_parse_json(text: str) -> Optional[ParsedAnalysis]:
    """Try to parse as JSON response."""
    cleaned = _clean_json_text(text)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    result = ParsedAnalysis()

    # task_codes
    raw_codes = data.get('task_codes', [])
    if isinstance(raw_codes, str):
        raw_codes = [raw_codes]
    result.task_codes = [c for c in raw_codes if c in VALID_TASK_CODES]

    # If no task_codes found, try to infer from tipo_servicio
    if not result.task_codes:
        tipo = data.get('tipo_servicio', '')
        if isinstance(tipo, str):
            inferred = _infer_task_codes_from_text(tipo)
            result.task_codes = inferred

    # date
    raw_date = data.get('fecha')
    if raw_date and raw_date != 'No disponible':
        result.date = _parse_date(str(raw_date))

    # km
    raw_km = data.get('km')
    if raw_km is not None and raw_km != 'No disponible':
        try:
            result.km = int(float(str(raw_km).replace('.', '').replace(',', '.')))
        except (ValueError, TypeError):
            pass

    # cost
    raw_cost = data.get('coste_total')
    if raw_cost is not None and raw_cost != 'No disponible':
        result.cost = _parse_cost(str(raw_cost))

    # notes_extra
    parts = []
    taller = data.get('taller')
    if taller and taller != 'No disponible':
        parts.append(f"Taller: {taller}")
    piezas = data.get('piezas')
    if piezas and piezas != 'No disponible':
        if isinstance(piezas, list):
            piezas = ', '.join(str(p) for p in piezas)
        parts.append(f"Piezas: {piezas}")
    obs = data.get('observaciones')
    if obs and obs != 'No disponible':
        parts.append(str(obs))
    result.notes_extra = '\n'.join(parts)

    return result


def _parse_regex_fallback(text: str) -> ParsedAnalysis:
    """Fallback parser using regex for unstructured text."""
    result = ParsedAnalysis()
    text_lower = text.lower()

    # task_codes from keywords
    result.task_codes = _infer_task_codes_from_text(text_lower)

    # date: DD/MM/YYYY or YYYY-MM-DD
    date_match = re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', text)
    if date_match:
        a, b, c = date_match.group(1), date_match.group(2), date_match.group(3)
        result.date = _parse_date(f"{a}/{b}/{c}")
    else:
        iso_match = re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', text)
        if iso_match:
            result.date = _parse_date(f"{iso_match.group(1)}-{iso_match.group(2)}-{iso_match.group(3)}")

    # km
    km_match = re.search(r'(\d[\d.]*)\s*(?:km|kilómetros|kilometros)', text_lower)
    if km_match:
        try:
            result.km = int(km_match.group(1).replace('.', ''))
        except ValueError:
            pass

    # cost
    cost_match = re.search(r'(\d[\d.,]*)\s*(?:€|EUR|euros)', text, re.IGNORECASE)
    if cost_match:
        result.cost = _parse_cost(cost_match.group(1))

    return result


def _infer_task_codes_from_text(text: str) -> list[str]:
    """Infer task codes from free text using keyword matching."""
    text_lower = text.lower()
    found = set()
    # Sort by length descending so longer phrases match first
    for keyword, code in sorted(KEYWORD_TO_TASK_CODE.items(), key=lambda x: -len(x[0])):
        if keyword in text_lower:
            found.add(code)
    return list(found)


def _parse_date(raw: str) -> Optional[date]:
    """Parse date from various formats."""
    raw = raw.strip()
    # YYYY-MM-DD
    match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    # DD/MM/YYYY
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', raw)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    return None


def _try_extract_json(text: str) -> Optional[list]:
    """Try to extract a JSON array from text that may contain surrounding prose."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def parse_catalog_items(raw_text: str) -> list[dict]:
    """Parse AI-generated catalog items from raw text.

    Returns a list of dicts with keys: task_code, name, description,
    interval_km, interval_months, is_safety_critical.
    """
    cleaned = _clean_json_text(raw_text)

    # Try direct JSON array parse
    data = None
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting embedded JSON array
    if data is None:
        data = _try_extract_json(cleaned)

    if not isinstance(data, list):
        return []

    items = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        task_code = entry.get('task_code')
        if not isinstance(task_code, str) or not task_code.strip():
            continue

        name = entry.get('name', task_code)
        if not isinstance(name, str):
            name = task_code

        description = entry.get('description', '')
        if not isinstance(description, str):
            description = ''

        raw_km = entry.get('interval_km')
        interval_km = None
        if raw_km is not None:
            try:
                interval_km = int(raw_km)
            except (ValueError, TypeError):
                pass

        raw_months = entry.get('interval_months')
        interval_months = None
        if raw_months is not None:
            try:
                interval_months = int(raw_months)
            except (ValueError, TypeError):
                pass

        is_safety_critical = bool(entry.get('is_safety_critical', False))

        items.append({
            'task_code': task_code.strip(),
            'name': name.strip(),
            'description': description.strip(),
            'interval_km': interval_km,
            'interval_months': interval_months,
            'is_safety_critical': is_safety_critical,
        })
    return items


def _parse_cost(raw: str) -> Optional[Decimal]:
    """Parse cost string to Decimal."""
    raw = raw.strip()
    raw = re.sub(r'[€$\s]', '', raw)
    raw = re.sub(r'EUR', '', raw, flags=re.IGNORECASE)
    # Handle European format: 1.234,56 → 1234.56
    if ',' in raw and '.' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    elif ',' in raw:
        raw = raw.replace(',', '.')
    try:
        return Decimal(raw).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return None

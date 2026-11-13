"""Definiciones operativas compartidas, independientes de la configuración regional del navegador."""
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PLANT_TIMEZONE = os.getenv('PLANT_TIMEZONE', 'America/Monterrey')
CLOSED = ('Entregado', 'Cancelado')
SOON_MINUTES = 30

def shift_at(utc_timestamp):
    local = utc_timestamp.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(PLANT_TIMEZONE))
    minute = local.hour * 60 + local.minute
    shift = 'T1' if 360 <= minute < 840 else 'T2' if 840 <= minute < 1290 else 'T3'
    operating_date = local.date() - timedelta(days=1) if minute < 360 else local.date()
    return {'shift': shift, 'date': operating_date.isoformat()}

def utc_period(start, end):
    """Fechas locales inclusivas convertidas a un intervalo UTC con inicio incluido y fin excluido."""
    zone = ZoneInfo(PLANT_TIMEZONE)
    lower = datetime.combine(start, datetime.min.time(), zone).astimezone(timezone.utc).replace(tzinfo=None) if start else None
    upper = datetime.combine(end + timedelta(days=1), datetime.min.time(), zone).astimezone(timezone.utc).replace(tzinfo=None) if end else None
    return lower, upper

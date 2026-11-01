"""Persist provider-reported usage; never infer token counts from text length."""

import logging

from ..database import SessionLocal
from ..models import ModelUsage

logger = logging.getLogger(__name__)


def usage_values(data: dict | None) -> tuple[int | None, int | None, int | None]:
    if not isinstance(data, dict):
        return None, None, None
    usage = data.get('usage')
    if not isinstance(usage, dict):
        return None, None, None

    def count(*names):
        for name in names:
            value = usage.get(name)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
        return None

    return (
        count('prompt_tokens', 'input_tokens'),
        count('completion_tokens', 'output_tokens'),
        count('total_tokens'),
    )


def record_usage(model: dict, usage: dict | None, source: str, task_id: int | None = None) -> None:
    input_tokens, output_tokens, total_tokens = usage_values({'usage': usage})
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    options = model.get('extra') or {}
    currency = options.get('price_currency')
    estimated_cost = None
    if currency in {'CNY', 'USD'} and input_tokens is not None and output_tokens is not None:
        try:
            input_price = float(options.get('input_price_per_million'))
            output_price = float(options.get('output_price_per_million'))
            if input_price >= 0 and output_price >= 0:
                estimated_cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
        except (TypeError, ValueError):
            pass
    try:
        with SessionLocal() as db:
            db.add(ModelUsage(
                model_config_id=model.get('id'), model_name=model['model_name'],
                provider=model.get('provider') or '', task_id=task_id, source=source,
                input_tokens=input_tokens, output_tokens=output_tokens,
                total_tokens=total_tokens, estimated_cost=estimated_cost,
                currency=currency if estimated_cost is not None else None,
            ))
            db.commit()
    except Exception:
        logger.exception('Unable to record model usage')

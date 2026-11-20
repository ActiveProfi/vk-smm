"""Ключ нейросети кабинета. В базе он лежит зашифрованным, как токен ВК."""
from __future__ import annotations

import os
from contextvars import ContextVar

_bound_kie: ContextVar[str] = ContextVar("bound_kie", default="")

MISSING_KIE = (
    "Нет ключа KIE. Откройте «Настройки данных» и впишите ключ. "
    "Без него тексты, картинки и контент-план не собираются."
)
MISSING_VK_TOKEN = (
    "Не задан токен ВК. Откройте «Каналы» → нужный канал → «Настройки» "
    "и вставьте токен группы."
)
MISSING_VK_GROUP = (
    "Не задан номер группы ВК. Откройте «Каналы» → нужный канал → «Настройки» "
    "и впишите ID группы."
)


def bind(user_id: int | None) -> str:
    """Запомнить ключ владельца команды на время запроса или фоновой задачи."""
    key = kie_for_user_id(user_id)
    _bound_kie.set(key)
    return key


def current_kie() -> str:
    bound = (_bound_kie.get() or "").strip()
    if bound:
        return bound
    return (os.environ.get("KIE_API_KEY") or "").strip()


def kie_for_user_id(user_id: int | None) -> str:
    env_key = (os.environ.get("KIE_API_KEY") or "").strip()
    if not user_id:
        return env_key
    try:
        from webapp.models import User, db
        from webapp.services import access as acc
        from webapp.services.secrets_box import reveal

        user = db.session.get(User, int(user_id))
        if not user:
            return env_key
        owner = db.session.get(User, acc.agency_owner_id(user)) or user
        stored = reveal(getattr(owner, "kie_api_key", "") or "")
        return stored or env_key
    except Exception:
        return env_key


def kie_is_saved(user_id: int | None) -> bool:
    if not user_id:
        return False
    try:
        from webapp.models import User, db
        from webapp.services import access as acc
        from webapp.services.secrets_box import reveal

        user = db.session.get(User, int(user_id))
        if not user:
            return False
        owner = db.session.get(User, acc.agency_owner_id(user)) or user
        return bool(reveal(getattr(owner, "kie_api_key", "") or ""))
    except Exception:
        return False

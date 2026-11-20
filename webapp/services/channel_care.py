"""Каналы команды: без личных пустышек и без одинаковых имён."""
from __future__ import annotations

AUTO_CHANNEL_NAME = "Мой канал"


def _name_key(name: str) -> str:
    return (name or "").strip().casefold()


def name_taken(owner_id: int, name: str, *, exclude_id: int | None = None) -> bool:
    """Такое название уже есть у активного канала этой команды."""
    from webapp.models import Workspace

    key = _name_key(name)
    if not key:
        return False
    rows = Workspace.query.filter_by(user_id=owner_id, is_active=True).all()
    for row in rows:
        if exclude_id and row.id == exclude_id:
            continue
        if _name_key(row.name) == key:
            return True
    return False


def _has_work(workspace_id: int) -> bool:
    from webapp.models import ContentPlanBatch, Draft

    if Draft.query.filter_by(workspace_id=workspace_id).first():
        return True
    if ContentPlanBatch.query.filter_by(workspace_id=workspace_id).first():
        return True
    return False


def retire_empty_staff_channels() -> None:
    """Пустые каналы, которые кабинет сам создал сотруднику, прячем.

    Строки в базе остаются. Если на таком канале уже есть посты или план,
    канал переходит владельцу команды, чтобы работа не пропала.
    """
    from webapp.models import TeamMember, User, Workspace, db

    members = TeamMember.query.filter_by(is_active=True).all()
    changed = False
    for member in members:
        user = db.session.get(User, member.user_id)
        login = ((user.username if user else "") or "сотрудник").strip()
        rows = Workspace.query.filter_by(user_id=member.user_id, is_active=True).all()
        for ws in rows:
            if not _has_work(ws.id):
                ws.is_active = False
                changed = True
                continue
            new_name = (ws.name or AUTO_CHANNEL_NAME).strip() or AUTO_CHANNEL_NAME
            if name_taken(member.agency_user_id, new_name):
                new_name = f"{new_name} — {login}"[:120]
            ws.name = new_name
            ws.user_id = member.agency_user_id
            changed = True
    if changed:
        db.session.commit()

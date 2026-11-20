"""Проверки правок после пользовательского теста кабинета."""
from webapp.models import Draft, User, Workspace, db
from webapp.services.user_keys import MISSING_KIE

from tests.conftest import add_member, login, make_user, make_workspace


def test_register_does_not_create_nameless_channel(app, client):
    response = client.post(
        "/auth/register",
        data={
            "username": "solo",
            "password": "password-123",
            "password2": "password-123",
            "privacy_agree": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert Workspace.query.count() == 0


def test_register_shows_russian_password_errors(client):
    short = client.post(
        "/auth/register",
        data={"username": "ab", "password": "short", "password2": "other"},
    )
    text = short.get_data(as_text=True)
    assert "Логин: от 3 до 80 символов." in text
    assert "Пароль: не меньше 8 символов." in text
    assert "Пароли не совпадают." in text
    assert "This field is required" not in text


def test_staff_has_no_personal_channel_and_opens_real_one(app, client):
    owner = make_user(app, "boss")
    manager = make_user(app, "manager", plan="free")
    make_workspace(app, owner, name="Кофейня")
    make_workspace(app, manager, name="Мой канал")
    add_member(app, owner, manager, "manager")
    login(client, "manager")
    page = client.get("/manager")
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Кофейня" in body
    assert body.count("Мой канал") == 0
    with app.app_context():
        personal = Workspace.query.filter_by(user_id=manager).all()
        assert personal
        assert all(row.is_active is False for row in personal)
        user = db.session.get(User, manager)
        active = user.get_active_workspace()
        assert active is not None
        assert active.name == "Кофейня"


def test_viewer_cannot_generate_even_on_own_named_channel(app, client):
    owner = make_user(app, "boss")
    viewer = make_user(app, "watcher", plan="free")
    clinic = make_workspace(app, owner, name="Клиника")
    own = make_workspace(app, viewer, name="Личный черновик")
    with app.app_context():
        db.session.add(
            Draft(user_id=viewer, workspace_id=own, topic="Не потерять", post_text="есть текст")
        )
        db.session.commit()
    add_member(app, owner, viewer, "viewer")
    login(client, "watcher")
    page = client.get("/generate")
    assert "только просмотр" in page.get_data(as_text=True).lower()
    denied = client.post(
        "/generate/start",
        data={"topic": "Проверка", "post_type": "expert", "materials": "Материалы для проверки прав."},
    )
    assert denied.status_code in {302, 403}
    with app.app_context():
        kept = db.session.get(Workspace, own)
        assert kept is not None
        assert kept.user_id == owner
        assert "Не потерять" in (kept.name + "") or Draft.query.filter_by(workspace_id=kept.id).count() == 1
        assert kept.name != "Клиника"
    home = client.get("/manager")
    assert "Клиника" in home.get_data(as_text=True)


def test_duplicate_channel_name_is_rejected(app, client):
    owner = make_user(app, "boss")
    make_workspace(app, owner, name="Пекарня")
    login(client, "boss")
    page = client.post(
        "/workspaces/new",
        data={
            "name": "Пекарня",
            "theme": "хлеб",
            "seed_mode": "empty",
            "package_code": "business",
            "submit": "Сохранить канал",
        },
    )
    assert "таким названием уже есть" in page.get_data(as_text=True)
    with app.app_context():
        assert Workspace.query.filter_by(user_id=owner, is_active=True).count() == 1


def test_queue_is_limited_to_selected_channel(app, client):
    owner = make_user(app, "boss")
    bakery = make_workspace(app, owner, name="Пекарня")
    auto = make_workspace(app, owner, name="Автосервис")
    with app.app_context():
        db.session.add_all(
            [
                Draft(
                    user_id=owner,
                    workspace_id=bakery,
                    topic="Утренний круассан",
                    status="planned",
                    scheduled_for="2026-12-02T09:00:00+10:00",
                ),
                Draft(
                    user_id=owner,
                    workspace_id=auto,
                    topic="Когда менять резину",
                    status="planned",
                    scheduled_for="2026-12-03T18:00:00+10:00",
                ),
            ]
        )
        user = db.session.get(Workspace, bakery).owner
        user.active_workspace_id = bakery
        db.session.commit()
    login(client, "boss")
    page = client.get("/generation-queue")
    text = page.get_data(as_text=True)
    assert "Утренний круассан" in text
    assert "Когда менять резину" not in text
    assert "Вариант B" not in text
    assert "сделаем панель менеджера" not in text
    assert "Пекарня" in text


def test_rubric_too_short_explains_why(app, client):
    owner = make_user(app, "boss")
    ws_id = make_workspace(app, owner, name="Пекарня")
    login(client, "boss")
    page = client.post(
        f"/workspaces/{ws_id}/rubrics/new",
        data={"title": "Сезон", "prompt_text": "мало", "sort_order": "1", "submit": "Сохранить рубрику"},
    )
    text = page.get_data(as_text=True)
    assert "слишком короткий" in text


def test_manual_plan_page_offers_hand_entry(app, client):
    owner = make_user(app, "boss")
    ws_id = make_workspace(app, owner, name="Пекарня")
    login(client, "boss")
    page = client.get(f"/workspaces/{ws_id}/content-plan")
    assert "Добавить тему самому" in page.get_data(as_text=True)


def test_missing_kie_message_points_to_settings():
    assert "Настройки данных" in MISSING_KIE
    assert ".env" not in MISSING_KIE

import asyncio
from types import SimpleNamespace

from bot.handlers import discover, user


class DummyMessage:
    def __init__(self, text="/start"):
        self.text = text
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


class DummyQueryMessage:
    def __init__(self):
        self.chat_id = 123


class DummyQuery:
    def __init__(self, data="dsc_showall"):
        self.data = data
        self.message = DummyQueryMessage()
        self.edits = []

    async def answer(self):
        return None

    async def edit_message_text(self, text, **kwargs):
        self.edits.append((text, kwargs))


class DummyUser:
    def __init__(self, user_id=123, username=None, first_name="Romi"):
        self.id = user_id
        self.username = username
        self.first_name = first_name


def make_update(text="/start", user_id=123):
    message = DummyMessage(text=text)
    return SimpleNamespace(
        effective_user=DummyUser(user_id=user_id),
        message=message,
        effective_chat=SimpleNamespace(id=user_id),
    )


def make_context():
    return SimpleNamespace(user_data={}, bot=SimpleNamespace())


def test_start_routes_existing_user_with_deep_link(monkeypatch):
    update = make_update(text="/start s_global", user_id=42)
    context = make_context()

    monkeypatch.setattr(user.user_service, "sync_identity", lambda _user: None)
    monkeypatch.setattr(user.user_service, "get_profile", lambda _uid: {"name": "A"})
    monkeypatch.setattr(user.user_service, "consume_pending_notifications", lambda _uid: [])

    called = {"discover": 0}

    async def fake_start_discover(*_args, **_kwargs):
        called["discover"] += 1

    monkeypatch.setattr(user, "start_discover", fake_start_discover)

    result = asyncio.run(user.start(update, context))

    assert result == -1
    assert called["discover"] == 1
    assert context.user_data.get("start_param") is None


def test_start_routes_after_profile_creation_with_deep_link(monkeypatch):
    update = make_update(text="/start s_global_newfriends", user_id=43)
    context = make_context()

    monkeypatch.setattr(user.user_service, "sync_identity", lambda _user: None)
    monkeypatch.setattr(user.user_service, "get_profile", lambda _uid: None)
    monkeypatch.setattr(user.user_service, "create_profile_from_context", lambda *_args, **_kwargs: None)

    called = {"discover": 0}

    async def fake_start_discover(*_args, **_kwargs):
        called["discover"] += 1

    monkeypatch.setattr(user, "start_discover", fake_start_discover)

    # mimic the profile completion path by setting the start_param and minimal profile fields
    context.user_data.update(
        {
            "start_param": "s_global_newfriends",
            "name": "B",
            "age": 21,
            "gender": "Cowok",
            "description": "hi",
            "latitude": 1.0,
            "longitude": 1.0,
            "photo_file_id": "photo",
        }
    )

    # Reuse the same logic through get_photo by providing the photo list and the fake create method.
    update.message.photo = [SimpleNamespace(file_id="photo")]
    asyncio.run(user.get_photo(update, context))

    assert called["discover"] == 1


def test_show_all_paginates_notifications(monkeypatch):
    query = DummyQuery(data="dsc_showall_p1")
    context = make_context()
    responder = DummyUser(user_id=77)

    actions = [
        {"_id": f"id{i}", "sender_telegram_id": 100 + i} for i in range(7)
    ]
    monkeypatch.setattr(
        discover.matching_service.discover_actions_repo,
        "list_pending_for_target",
        lambda _uid: actions,
    )
    monkeypatch.setattr(
        discover.user_service,
        "get_profile",
        lambda uid: {"name": f"User{uid}"} if uid else None,
    )

    asyncio.run(discover._handle_show_all(query, context, "p1", responder))

    assert query.edits
    text, kwargs = query.edits[-1]
    assert "halaman 2/2" in text
    reply_markup = kwargs["reply_markup"]
    # 5 buttons for page 2? page=1 means second page, so 2 entries plus nav + ignore.
    assert len(reply_markup.inline_keyboard[0]) == 1
    assert len(reply_markup.inline_keyboard[-1]) == 1

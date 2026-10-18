from __future__ import annotations

import io
import json
import pathlib

import pytest
import respx

import popnow
from popnow import PopNow

from .conftest import BASE, envelope

UPLOAD_URL = "https://uploads.example.com/put/fil_1?sig=abc"

TICKET = {
    "fileId": "fil_1",
    "key": "popnow://f/fil_1",
    "uploadUrl": UPLOAD_URL,
    "method": "PUT",
    "headers": {"Content-Type": "image/png", "Content-Length": "8"},
    "expiresAt": "2026-10-16T09:20:00Z",
    "maxBytes": 8,
}

COMMITTED = {
    "fileId": "fil_1",
    "status": "ready",
    "bytes": 8,
    "contentType": "image/png",
    "sha256": "0" * 64,
    "uri": "popnow://f/fil_1",
    "expiresAt": "2026-10-17T09:12:00Z",
    "width": 1,
    "height": 1,
}

PNG = b"\x89PNG\r\n\x1a\n"


def test_upload_path_runs_ticket_put_commit(mock: respx.MockRouter, client: PopNow, tmp_path: pathlib.Path) -> None:
    path = tmp_path / "reference.png"
    path.write_bytes(PNG)
    ticket = mock.post(f"{BASE}/api/v1/common/upload-url").respond(200, json=envelope(TICKET))
    put = mock.put(UPLOAD_URL).respond(200)
    commit = mock.post(f"{BASE}/api/v1/files/fil_1/commit").respond(200, json=envelope(COMMITTED))

    uploaded = client.files.upload(path)

    assert json.loads(ticket.calls.last.request.content) == {"contentType": "image/png", "bytes": 8}
    put_request = put.calls.last.request
    assert put_request.content == PNG
    assert put_request.headers["content-type"] == "image/png"
    assert put_request.headers["content-length"] == "8"
    assert "authorization" not in put_request.headers  # the signed URL is the permission
    assert put_request.headers["user-agent"].startswith("popnow-python/")
    assert commit.called
    assert uploaded.uri == "popnow://f/fil_1"
    assert uploaded.width == 1


def test_upload_bytes_and_file_object(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/common/upload-url").respond(200, json=envelope(TICKET))
    put = mock.put(UPLOAD_URL).respond(200)
    mock.post(f"{BASE}/api/v1/files/fil_1/commit").respond(200, json=envelope(COMMITTED))

    assert client.files.upload(PNG, content_type="image/png").uri == "popnow://f/fil_1"
    assert client.files.upload(io.BytesIO(PNG), content_type="image/png").file_id == "fil_1"
    assert put.call_count == 2


def test_upload_requires_content_type(client: PopNow) -> None:
    with pytest.raises(ValueError, match="content_type"):
        client.files.upload(b"data")


def test_upload_put_failure_raises(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/common/upload-url").respond(200, json=envelope(TICKET))
    mock.put(UPLOAD_URL).respond(403, text="SignatureDoesNotMatch")
    with pytest.raises(popnow.APIError) as info:
        client.files.upload(PNG, content_type="image/png")
    assert info.value.status_code == 403


def test_commit_mismatch_maps_to_bad_request(mock: respx.MockRouter, client: PopNow) -> None:
    mock.post(f"{BASE}/api/v1/files/fil_1/commit").respond(400, json=envelope(code=40003, msg="Mismatch"))
    with pytest.raises(popnow.BadRequestError) as info:
        client.files.commit("fil_1")
    assert info.value.code == 40003


def test_import_lora(mock: respx.MockRouter, client: PopNow) -> None:
    route = mock.post(f"{BASE}/api/v1/files/import").respond(
        200, json=envelope(dict(COMMITTED, contentType="application/octet-stream"))
    )
    result = client.files.import_lora("your-name/your-lora-repo", token="hf_x")
    assert json.loads(route.calls.last.request.content) == {"url": "your-name/your-lora-repo", "token": "hf_x"}
    assert result.uri.startswith("popnow://f/")


def test_download_streams_without_api_key(mock: respx.MockRouter, client: PopNow, tmp_path: pathlib.Path) -> None:
    url = "https://media.example.com/signed/out_0.png"
    route = mock.get(url).respond(200, content=PNG)
    saved = client.files.download(url, tmp_path)
    assert saved == tmp_path / "out_0.png"
    assert saved.read_bytes() == PNG
    assert "authorization" not in route.calls.last.request.headers
    assert route.calls.last.request.headers["user-agent"].startswith("popnow-python/")


def test_assets_crud(mock: respx.MockRouter, client: PopNow) -> None:
    asset = {
        "id": "ast_1",
        "uri": "popnow://a/ast_1",
        "name": "Hero shot",
        "kind": "image",
        "contentType": "image/png",
        "bytes": 1000,
        "source": "task_output",
        "sourceId": "job_1",
        "createdAt": "2026-10-16T00:00:00Z",
        "updatedAt": "2026-10-16T00:00:00Z",
        "previewUrl": "https://media.example.com/preview",
        "favorite": False,
        "model": "alibaba/z-image-turbo/text-to-image",
        "modelName": "Z-Image Turbo",
    }
    create = mock.post(f"{BASE}/api/v1/assets").respond(200, json=envelope(asset))
    listing = mock.get(f"{BASE}/api/v1/assets").respond(200, json=envelope({"items": [asset]}))
    patch = mock.patch(f"{BASE}/api/v1/assets/ast_1").respond(200, json=envelope(dict(asset, favorite=True)))
    delete = mock.delete(f"{BASE}/api/v1/assets/ast_1").respond(200, json=envelope({"id": "ast_1", "deleted": True}))

    saved = client.assets.save_task_output("job_1", name="Hero shot")
    request = create.calls.last.request
    assert json.loads(request.content) == {"source": "task_output", "taskId": "job_1", "index": 0, "name": "Hero shot"}
    assert request.headers["idempotency-key"]  # required by the API, generated when omitted
    assert saved.uri == "popnow://a/ast_1"
    assert saved.model_name == "Z-Image Turbo"

    page = client.assets.list(kind="image", source=["task_output", "upload"], favorite=False, sort="name")
    params = listing.calls.last.request.url.params
    assert params["source"] == "task_output,upload"
    assert params["favorite"] == "false"
    assert params["sort"] == "name"
    assert [a.id for a in page] == ["ast_1"]
    assert page.next_cursor is None

    updated = client.assets.update("ast_1", favorite=True)
    assert json.loads(patch.calls.last.request.content) == {"favorite": True}
    assert updated.favorite is True

    assert client.assets.delete("ast_1").deleted is True
    assert delete.called

    with pytest.raises(ValueError):
        client.assets.update("ast_1")
    with pytest.raises(ValueError):
        client.assets.create(source="ftp")


def test_assets_characters_and_usage(mock: respx.MockRouter, client: PopNow) -> None:
    character = {
        "id": "ent_1",
        "kind": "character",
        "name": "Captain",
        "note": "",
        "coverAssetId": "",
        "cover": None,
        "assets": [],
        "count": 0,
        "createdAt": "2026-10-16T00:00:00Z",
        "updatedAt": "2026-10-16T00:00:00Z",
    }
    mock.get(f"{BASE}/api/v1/assets/entities").respond(200, json=envelope({"items": [character]}))
    mock.get(f"{BASE}/api/v1/assets/entities/ent_1").respond(200, json=envelope(character))
    mock.get(f"{BASE}/api/v1/assets/usage").respond(
        200,
        json=envelope(
            {
                "tier": {"id": "free", "name": "Free", "minTopupUsd": "0", "maxBytes": 0, "maxCount": 0, "maxFileBytes": 0},
                "usage": {"count": 0, "bytes": 0},
                "limits": {},
                "full": True,
                "nextTier": None,
                "tiers": [],
                "dailyCreateLimit": 100,
                "createdToday": 0,
                "scope": {"workspaceId": "", "personal": True, "role": "owner", "canWrite": True, "canTopUp": True},
            }
        ),
    )
    assert client.assets.list_characters().items[0].name == "Captain"
    assert client.assets.get_character("ent_1").cover is None
    usage = client.assets.usage()
    assert usage.full is True and usage.daily_create_limit == 100
    assert usage.tier is not None and usage.tier["name"] == "Free"

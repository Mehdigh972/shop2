import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from garena_topup import GarenaTopupSession

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "config.env")

NOVNC_URL = os.getenv("NOVNC_URL", "")
API_KEY = os.getenv("HELPER_API_KEY", "")
GARENA_DOMAIN = os.getenv("GARENA_DOMAIN", "shop2game.com")
HEADLESS = os.getenv("HEADLESS", "1").lower() not in ("0", "false", "no")
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "") or None

app = FastAPI(title="FreeFire Shop Helper API")


class PlayerCheckRequest(BaseModel):
    player_id: str = Field(min_length=5)


class RedeemSubmitRequest(BaseModel):
    player_id: str = Field(min_length=5)
    voucher_code: str = Field(min_length=4)


def require_api_key(x_api_key: str | None):
    if not API_KEY or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def is_captcha_like(message: str):
    text = str(message or "").lower()
    return any(
        word in text
        for word in [
            "captcha",
            "verification",
            "verify",
            "cloudflare",
            "challenge",
            "datadome",
            "http 403",
            "forbidden",
        ]
    )


def make_error_payload(player_id: str, message: str):
    payload = {
        "ok": False,
        "player_id": player_id,
        "status": "captcha_required" if is_captcha_like(message) else "error",
        "message": message,
    }
    if payload["status"] == "captcha_required" and NOVNC_URL:
        payload["manual_url"] = NOVNC_URL
    return payload


def lookup_player(player_id: str):
    session = GarenaTopupSession(
        domain=GARENA_DOMAIN,
        headless=HEADLESS,
        executable_path=CHROMIUM_PATH,
    )
    try:
        session.start()
        nickname = session.login_player(player_id)
        if nickname:
            return {
                "ok": True,
                "status": "ok",
                "player_id": player_id,
                "nickname": nickname,
                "player_name": nickname,
            }
        return {"ok": False, "status": "error", "player_id": player_id, "message": "nickname not found"}
    except Exception as exc:
        return make_error_payload(player_id, str(exc))
    finally:
        try:
            session.close()
        except Exception:
            pass


def redeem_code(player_id: str, voucher_code: str):
    session = GarenaTopupSession(
        domain=GARENA_DOMAIN,
        headless=HEADLESS,
        executable_path=CHROMIUM_PATH,
    )
    try:
        session.start()
        nickname = session.login_player(player_id)
        if not nickname:
            return {"ok": False, "status": "error", "player_id": player_id, "message": "nickname not found"}

        result = session.redeem_voucher(voucher_code)
        return {
            "ok": bool(result.get("success")),
            "status": "success" if result.get("success") else "failed",
            "player_id": player_id,
            "nickname": nickname,
            "player_name": nickname,
            "message": result.get("message", "Transaction status unknown."),
            "screenshot": result.get("screenshot"),
        }
    except Exception as exc:
        payload = make_error_payload(player_id, str(exc))
        payload["voucher_code_suffix"] = voucher_code[-4:] if len(voucher_code) >= 4 else voucher_code
        return payload
    finally:
        try:
            session.close()
        except Exception:
            pass


@app.get("/health")
def health(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    return {"ok": True, "service": "freefire-shop-helper"}


@app.post("/freefire/player/check")
def player_check(payload: PlayerCheckRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    player_id = payload.player_id.replace(" ", "")
    if not player_id.isdigit():
        raise HTTPException(status_code=422, detail="player_id must be numeric")
    return lookup_player(player_id)


@app.post("/freefire/redeem/submit")
def redeem_submit(payload: RedeemSubmitRequest, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    player_id = payload.player_id.replace(" ", "")
    voucher_code = payload.voucher_code.replace(" ", "").replace("-", "")
    if not player_id.isdigit():
        raise HTTPException(status_code=422, detail="player_id must be numeric")
    if len(voucher_code) < 4:
        raise HTTPException(status_code=422, detail="voucher_code is too short")
    return redeem_code(player_id, voucher_code)

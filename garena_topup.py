import os
import logging
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GarenaTopupSession:
    """
    Manages a browser session using Playwright to interact with Garena Top-up Center
    for Free Fire nickname verification and voucher PIN redemption.
    """

    def __init__(self, domain="shop2game.com", headless=True, executable_path=None):
        self.domain = domain
        self.headless = headless
        self.executable_path = executable_path if executable_path else None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.nickname = None
        self.player_id = None

    def start(self):
        """Starts the Playwright browser session."""
        logging.info("Starting browser session...")
        self.playwright = sync_playwright().start()

        launch_args = {
            "headless": self.headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
            ],
        }

        # Specify system chromium path for Raspberry Pi (ARM) if provided.
        if self.executable_path:
            logging.info(f"Using custom browser path: {self.executable_path}")
            launch_args["executable_path"] = self.executable_path

        self.browser = self.playwright.chromium.launch(**launch_args)

        self.context = self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale=os.getenv("BROWSER_LOCALE", "en-US"),
        )
        self.page = self.context.new_page()

        # Shop2Game currently renders a blank page in some environments when
        # playwright-stealth is applied. Keep it optional instead of default-on.
        if os.getenv("USE_PLAYWRIGHT_STEALTH", "0").lower() in ("1", "true", "yes"):
            stealth_sync(self.page)
            logging.info("Playwright stealth enabled.")

        logging.info("Browser session started successfully.")

    def login_player(self, player_id):
        """
        Navigates to Garena top-up page, inputs the Player ID, submits the form,
        and extracts the customer's in-game nickname.
        """
        self.player_id = player_id
        auth_errors = []

        def capture_auth_response(response):
            if "/api/auth/player_id_login" not in response.url:
                return
            if response.status >= 400:
                try:
                    body = response.text()[:500]
                except Exception:
                    body = ""
                auth_errors.append(f"Shop2Game player_id_login returned HTTP {response.status}. {body}")

        self.page.on("response", capture_auth_response)

        url = f"https://{self.domain}/app?game=100067"
        logging.info(f"Navigating to login page: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try:
            self.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            logging.info("Network did not become fully idle; continuing after DOM load.")
        self.page.wait_for_timeout(3000)

        # Step 1: Click Player ID login option if a chooser is visible.
        try:
            player_id_btn_selectors = [
                'text="Player ID"',
                'text="Player ID Login"',
                'text="شناسه بازیکن"',
                'text="شناسه کاربر"',
                'text="معرّف الاعب"',
                'text="ID"',
                '.login_btn',
                'div[class*="player_id"]',
            ]
            clicked = False
            for opt in player_id_btn_selectors:
                btn = self.page.locator(opt).first
                if btn.is_visible():
                    btn.click()
                    clicked = True
                    logging.info(f"Clicked Player ID button using selector: {opt}")
                    break
            if not clicked:
                logging.info("Player ID selection button not found, assuming directly on Player ID input screen.")
        except Exception as e:
            logging.warning(f"Error searching for Player ID login button: {e}")

        self.page.wait_for_timeout(1500)
        try:
            self.page.wait_for_selector('input[type="text"], input[type="number"]', timeout=15000)
        except Exception:
            logging.warning("Timed out waiting for player ID input to render.")

        # Step 2: Locate and fill the Player ID input field.
        input_selectors = [
            'input[placeholder*="Player ID"]',
            'input[placeholder*="player" i]',
            'input[placeholder*="ID"]',
            'input[placeholder*="شناسه"]',
            'input[placeholder*="معرف"]',
            'input[placeholder*="اللاعب"]',
            'input[type="text"]',
            'input[type="number"]',
            '.login-input input',
        ]

        player_input = None
        for selector in input_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    player_input = el
                    logging.info(f"Found input field using selector: {selector}")
                    break
            except Exception:
                continue

        if not player_input:
            self.page.screenshot(path="error_finding_input.png")
            raise Exception("Could not find Player ID input field on the page.")

        player_input.click()
        player_input.fill(str(player_id))
        self.page.wait_for_timeout(500)

        # Step 3: Click the login/submit button.
        login_btn_selectors = [
            'button[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("ورود")',
            'button:has-text("تسجيل الدخول")',
            'button:has-text("تسجيل")',
            'input[type="submit"]',
            '.login-btn',
            'button.primary-btn',
        ]

        login_btn = None
        for selector in login_btn_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    login_btn = el
                    logging.info(f"Found Login button using selector: {selector}")
                    break
            except Exception:
                continue

        if not login_btn:
            raise Exception("Could not find Login button.")

        login_btn.click()
        try:
            self.page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            logging.info("Network did not become fully idle after login click.")
        self.page.wait_for_timeout(4000)

        if auth_errors:
            raise Exception("Captcha or verification required: " + auth_errors[-1])

        # Step 4: Extract the nickname / verify success.
        nickname_selectors = [
            '.player-name',
            '.nickname',
            '.user-name',
            '.profile-name',
            'span[class*="name"]',
            'div[class*="name"]',
            'span[class*="nickname"]',
            '#player-name',
            '#nickname',
            '.profile_nickname',
        ]

        nickname = None
        for selector in nickname_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    nickname = el.inner_text().strip()
                    if nickname:
                        logging.info(f"Extracted nickname: {nickname} using selector: {selector}")
                        break
            except Exception:
                continue

        # Backup check in window state / storage.
        if not nickname:
            try:
                nickname = self.page.evaluate(
                    "() => window.player_nickname || localStorage.getItem('player_nickname') || sessionStorage.getItem('player_nickname')"
                )
            except Exception:
                pass

        if not nickname:
            error_selectors = [
                'div.error',
                'span.error',
                '.alert-danger',
                'text="not found"',
                'text="یافت نشد"',
                'text="غير صالح"',
            ]
            for err_sel in error_selectors:
                try:
                    el = self.page.locator(err_sel).first
                    if el.is_visible():
                        raise Exception(f"Login failed: {el.inner_text().strip()}")
                except Exception:
                    continue

            screenshot_path = f"login_failed_{player_id}.png"
            self.page.screenshot(path=screenshot_path)
            raise Exception(f"Login completed but nickname not found. Check screenshot: {screenshot_path}")

        self.nickname = nickname
        return nickname

    def redeem_voucher(self, voucher_code):
        """
        Navigates to the Garena Voucher/PPC page, inputs the voucher PIN,
        submits it, and parses the success/failure message.
        """
        if not self.page:
            raise Exception("No active session. Make sure player is logged in first.")

        voucher_btn_selectors = [
            'text="Garena PPC"',
            'text="Garena Voucher"',
            'text="Garena PPC/Voucher"',
            'text="بطاقة غارينا"',
            'text="کارت غارینا"',
            'div[class*="garena_ppc"]',
            'div[class*="voucher"]',
            'img[alt*="Garena"]',
            'img[alt*="Voucher"]',
        ]

        voucher_btn = None
        for selector in voucher_btn_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    voucher_btn = el
                    logging.info(f"Found Voucher option using selector: {selector}")
                    break
            except Exception:
                continue

        if not voucher_btn:
            self.page.screenshot(path="payment_methods_error.png")
            raise Exception("Could not find Garena Voucher payment option on this page.")

        voucher_btn.click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

        pin_input_selectors = [
            'input[placeholder*="Card Password"]',
            'input[placeholder*="Card PIN"]',
            'input[placeholder*="کد"]',
            'input[placeholder*="رمز"]',
            'input[type="text"]',
            'input[type="password"]',
            '.card-pin input',
        ]

        pin_input = None
        for selector in pin_input_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    pin_input = el
                    logging.info(f"Found PIN input field using: {selector}")
                    break
            except Exception:
                continue

        if not pin_input:
            self.page.screenshot(path="pin_input_error.png")
            raise Exception("Could not find Garena Card PIN input field.")

        pin_input.fill(str(voucher_code))
        self.page.wait_for_timeout(500)

        confirm_btn_selectors = [
            'button[type="submit"]',
            'button:has-text("Confirm")',
            'button:has-text("تایید")',
            'button:has-text("تأكيد")',
            'input[type="submit"]',
            '.confirm-btn',
            'button.primary-btn',
        ]

        confirm_btn = None
        for selector in confirm_btn_selectors:
            try:
                el = self.page.locator(selector).first
                if el.is_visible():
                    confirm_btn = el
                    logging.info(f"Found Redeem Confirm button using: {selector}")
                    break
            except Exception:
                continue

        if not confirm_btn:
            raise Exception("Could not find redemption confirm button.")

        confirm_btn.click()
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(5000)

        page_text = self.page.inner_text("body")
        result_screenshot = f"result_{self.player_id}_{voucher_code[-4:] if len(voucher_code) > 4 else voucher_code}.png"
        self.page.screenshot(path=result_screenshot)
        logging.info(f"Transaction completed. Result screenshot saved to {result_screenshot}")

        success_keywords = ["successful", "success", "نجاح", "موفق", "تراکنش با موفقیت", "transaction successful", "done"]
        failed_keywords = ["invalid", "already used", "expired", "error", "خطا", "نامعتبر", "استفاده شده", "fail", "wrong"]

        is_success = False
        result_message = "Transaction status uncertain. Check screenshot."

        for kw in success_keywords:
            if kw in page_text.lower():
                is_success = True
                result_message = "Top-up completed successfully!"
                break

        if not is_success:
            for kw in failed_keywords:
                if kw in page_text.lower():
                    try:
                        err_text = self.page.locator('div[class*="error"], span[class*="error"], .alert-danger').inner_text()
                        if err_text:
                            result_message = f"Failed: {err_text.strip()}"
                            break
                    except Exception:
                        pass
                    result_message = "Failed: Invalid PIN, card already used, or expired."
                    break

        return {
            "success": is_success,
            "message": result_message,
            "screenshot": result_screenshot,
        }

    def close(self):
        """Cleans up the Playwright browser and context resources."""
        logging.info("Closing browser session...")
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logging.info("Browser session closed cleanly.")
        except Exception as e:
            logging.error(f"Error while closing browser session: {e}")

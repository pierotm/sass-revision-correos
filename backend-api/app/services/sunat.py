import asyncio
import logging
from playwright.async_api import async_playwright
from shared.security import security_manager
from datetime import datetime
import os
import traceback
import hashlib

logger = logging.getLogger(__name__)

class SunatService:
    def __init__(self):
        self.login_url = "https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm"

    async def _get_browser(self):
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        return browser, page

    async def test_connection(self, ruc: str, user: str, password_encrypted: str):
        max_attempts = 2
        last_result = {"success": False, "message": "No attempts made"}

        for attempt in range(1, max_attempts + 1):
            browser, page = await self._get_browser()
            try:
                # 0. Decrypt password
                password = security_manager.decrypt_password(password_encrypted)
                
                # 1. Login with 45s timeout
                logger.info(f"Attempt {attempt}/{max_attempts} - Navigating to SUNAT login...")
                await page.goto(self.login_url, wait_until="networkidle", timeout=45000)
                
                await page.fill("#txtRuc", ruc)
                await page.fill("#txtUsuario", user)
                await page.fill("#txtContrasena", password)
                
                logger.info("Clicking Accept...")
                await page.click("#btnAceptar")
                
                # 2. Navigation to Mailbox (Critical Step 45s)
                logger.info("Navigating to Mailbox...")
                try:
                    async with page.expect_popup(timeout=20000) as popup_info:
                        await page.click("text='Buzón Electrónico'", force=True)
                    page = await popup_info.value
                    logger.info("New tab detected, switching context...")
                except:
                    logger.info("Staying in current page.")
                
                # 3. Entering Iframe (Critical Step 60s)
                logger.info("Entering Mailbox Iframe...")
                await page.wait_for_load_state("networkidle", timeout=60000)
                iframe_element = await page.wait_for_selector("iframe[name='iframeApplication']", timeout=60000)
                frame = page.frame(name="iframeApplication")
                
                if not frame:
                    raise Exception("iframeApplication NOT found")

                # 4. Deep Navigation (Critical Step 45s)
                logger.info("Opening Buzón Notificaciones...")
                await frame.wait_for_timeout(2000)
                await frame.click("text=Buzón Notificaciones")
                
                await frame.wait_for_selector("text=/ASUNTO:/i", timeout=45000)
                
                items = await frame.query_selector_all("text=/ASUNTO:/i")
                asunto_text = await items[0].inner_text()
                asunto = asunto_text.split("\n")[0] if "\n" in asunto_text else asunto_text

                await items[0].click()
                await frame.wait_for_timeout(3000) 
                
                # 5. Download (Critical Step 45s)
                logger.info("Triggering PDF download...")
                pdf_link = await frame.wait_for_selector("a:has-text('constancia_')", timeout=45000)
                async with page.expect_download() as download_info:
                    await pdf_link.click()
                
                download = await download_info.value
                doc_dir = f"/app/storage/documents/{ruc}"
                os.makedirs(doc_dir, exist_ok=True)
                
                filename = download.suggested_filename
                file_path = os.path.join(doc_dir, filename)
                await download.save_as(file_path)
                
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    content = f.read()
                    sha256_hash.update(content)
                file_hash = sha256_hash.hexdigest()
                
                logger.info(f"SUCCESS on attempt {attempt}: {filename}")
                return {
                    "success": True, 
                    "message": "File download successful",
                    "data": {
                        "asunto": asunto.strip(),
                        "filename": filename,
                        "file_hash": file_hash,
                        "file_path": file_path,
                        "size": len(content)
                    }
                }

            except Exception as e:
                error_msg = str(e)
                error_type = "UNKNOWN"
                if "Timeout" in error_msg:
                    if "iframeApplication" in error_msg: error_type = "IFRAME_TIMEOUT"
                    elif "Buzón" in error_msg: error_type = "LOGIN_REDIRECT_TIMEOUT"
                    else: error_type = "NETWORK_TIMEOUT"
                elif "selector" in error_msg.lower(): error_type = "SELECTOR_NOT_FOUND"
                
                logger.warning(f"Attempt {attempt} failed [{error_type}]: {error_msg}")
                
                # Screenshot on final failure or unknown error
                if attempt == max_attempts or error_type == "UNKNOWN":
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_path = f"/app/storage/screenshots/error_deep_{ruc}_{timestamp}.png"
                    await page.screenshot(path=screenshot_path)
                    
                    last_result = {
                        "success": False, 
                        "error_type": error_type,
                        "message": error_msg,
                        "stack_trace": traceback.format_exc(),
                        "screenshot_path": screenshot_path
                    }
                else:
                    logger.info("Waiting 10s for backoff...")
                    await asyncio.sleep(10)
            finally:
                await browser.close()
        
        return last_result

sunat_service = SunatService()

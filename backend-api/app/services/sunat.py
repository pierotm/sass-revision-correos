import logging
from playwright.async_api import async_playwright
from shared.security import SecurityManager
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SunatService:
    def __init__(self):
        self.security = SecurityManager()
        self.login_url = "https://e-menu.sunat.gob.pe/cl-ti-itmenu/MenuInternet.htm"

    async def test_connection(self, ruc: str, user: str, password_encrypted: str) -> Dict[str, Any]:
        """
        Attempts to login to SUNAT to verify credentials.
        """
        password = self.security.decrypt(password_encrypted)
        
        async with async_playwright() as p:
            # Enhanced evasion
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            
            # Stealth: Add extra headers
            await page.set_extra_http_headers({
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            })
            
            try:
                logger.info(f"Navigating to SUNAT login: {self.login_url}")
                await page.goto(self.login_url, wait_until="networkidle", timeout=60000)
                
                # Debug screenshot
                debug_path = f"/app/storage/screenshots/debug_load_{ruc}.png"
                await page.screenshot(path=debug_path)
                logger.info(f"Debug screenshot saved to {debug_path}")
                
                logger.info(f"Page loaded. Filling credentials for RUC {ruc}...")
                # Real selectors identified:
                await page.fill("#txtRuc", ruc)
                await page.wait_for_timeout(800) # Small pause
                
                await page.fill("#txtUsuario", user)
                await page.wait_for_timeout(1000) # Small pause
                
                await page.fill("#txtContrasena", password)
                await page.wait_for_timeout(1500) # Wait before clicking
                
                logger.info("Clicking Accept...")
                await page.click("#btnAceptar")
                
                logger.info("Waiting for SUNAT response and navigating to Mailbox...")
                # 1. Click on Buzón Electrónico (Top Header) - Use text for robustness
                await page.wait_for_selector("text='Buzón Electrónico'", timeout=20000)
                await page.click("text='Buzón Electrónico'")
                
                logger.info("Entering Mailbox Iframe...")
                # 2. Wait for the iframe to load and switch context
                # Sometimes it takes a while to appear
                iframe_element = await page.wait_for_selector("iframe[name='iframeApplication']", timeout=30000)
                frame = page.frame(name="iframeApplication")
                
                if not frame:
                    # Fallback if name is not set correctly
                    frame = await iframe_element.content_frame()
                
                # 3. Inside the frame, navigate to Buzón Notificaciones
                logger.info("Navigating to Buzón Notificaciones inside iframe...")
                await frame.wait_for_timeout(2000) # Give scripts time to initialize
                await frame.click("text=Buzón Notificaciones")
                
                # 4. Extract the first notification
                logger.info("Waiting for notification list content...")
                # Wait explicitly for the text 'ASUNTO:' to appear inside the list
                await frame.wait_for_selector("text=/ASUNTO:/i", timeout=20000)
                
                # Identify the first notification item
                items = await frame.query_selector_all("text=/ASUNTO:/i")
                if not items:
                    raise Exception("No notifications found with 'ASUNTO:' text after waiting")
                
                asunto_text = await items[0].inner_text()
                # Extract subject and date from text if possible
                asunto = asunto_text.split("\n")[0] if "\n" in asunto_text else asunto_text

                # Click to open the detail (usually the parent or the text itself)
                await items[0].click()
                await frame.wait_for_timeout(3000) # Wait for detail panel
                
                # 5. Download the PDF
                logger.info("Triggering PDF download...")
                pdf_link = await frame.wait_for_selector("a:has-text('constancia_')", timeout=10000)
                async with page.expect_download() as download_info:
                    await pdf_link.click()
                
                download = await download_info.value
                
                # Define local path
                doc_dir = f"/app/storage/documents/{ruc}"
                import os
                os.makedirs(doc_dir, exist_ok=True)
                
                filename = download.suggested_filename
                file_path = os.path.join(doc_dir, filename)
                await download.save_as(file_path)
                
                # 6. Calculate Hash and Validate PDF
                import hashlib
                sha256_hash = hashlib.sha256()
                with open(file_path, "rb") as f:
                    content = f.read()
                    sha256_hash.update(content)
                
                file_hash = sha256_hash.hexdigest()
                
                # Validate PDF magic number (%PDF-)
                is_pdf = content.startswith(b"%PDF-")
                
                if not is_pdf:
                    logger.error(f"Downloaded file is NOT a PDF: {filename}")
                    return {"success": False, "message": "Downloaded file is invalid (not a PDF)"}

                logger.info(f"Download successful: {filename} (Hash: {file_hash[:10]}...)")
                
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
                # Capture screenshot on failure
                import os
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"/app/storage/screenshots/error_deep_{ruc}_{timestamp}.png"
                await page.screenshot(path=screenshot_path)
                logger.error(f"Deep navigation error: {str(e)}. Screenshot: {screenshot_path}")
                return {"success": False, "message": f"Deep navigation failed: {str(e)}"}
            finally:
                await browser.close()

sunat_service = SunatService()

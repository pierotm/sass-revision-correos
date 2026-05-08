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
            # We use a real user agent to avoid basic blocks
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                logger.info(f"Navigating to SUNAT login: {self.login_url}")
                await page.goto(self.login_url, wait_until="networkidle", timeout=60000)
                
                logger.info(f"Page loaded. Filling credentials for RUC {ruc}...")
                # Note: These selectors are placeholders for the actual SUNAT ones
                # RUC login tab usually needs to be active
                await page.fill("#txtRuc", ruc)
                await page.fill("#txtUsuario", user)
                await page.fill("#txtClave", password)
                
                logger.info("Clicking Accept...")
                await page.click("#btnAceptar")
                
                logger.info("Waiting for response...")
                await page.wait_for_timeout(5000) 
                
                content = await page.content()
                if "Bienvenido" in content or await page.query_selector("#btnSiguiente"):
                    logger.info("Login successful!")
                    return {"success": True, "message": "Login successful"}
                
                error_element = await page.query_selector(".error") 
                if error_element:
                    error_text = await error_element.inner_text()
                    logger.warning(f"Login failed: {error_text}")
                    return {"success": False, "message": f"SUNAT Error: {error_text}"}
                
                logger.warning("Unknown state after login attempt.")
                return {"success": False, "message": "Unknown error during login"}
                
            except Exception as e:
                logger.error(f"Playwright error: {str(e)}")
                return {"success": False, "message": f"Connection failed: {str(e)}"}
            finally:
                await browser.close()

sunat_service = SunatService()

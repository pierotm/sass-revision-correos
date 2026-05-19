import asyncio
import logging
from playwright.async_api import async_playwright
from shared.security import security_manager
from datetime import datetime
import os
import traceback
import hashlib
import re

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
                
                # Resilient extraction of attachment links
                # We find all <a> links and check if they either point to the download endpoint
                # OR if their text matches the pattern of a SUNAT attachment (like a purely numeric resolution ID or 'constancia_')
                all_links = await frame.query_selector_all("a")
                logger.info(f"Found {len(all_links)} total links in iframe.")
                
                download_candidates = []
                for el in all_links:
                    text = (await el.inner_text() or "").strip()
                    href = (await el.get_attribute("href") or "").strip()
                    onclick = (await el.get_attribute("onclick") or "").strip()
                    
                    has_digits_id = bool(re.search(r'\d{8,}', text)) and " " not in text
                    
                    is_candidate = (
                        "/visor/bajarArchivo/" in href or
                        "/visor/bajarArchivo/" in onclick or
                        "constancia_" in text.lower() or
                        has_digits_id
                    )
                    
                    # Avoid navigation links that might be numeric but are pagination (though unlikely to have 8 digits)
                    if is_candidate and not any(word in text.lower() for word in ["volver", "imprimir", "salir", "ayuda", "asunto"]):
                        # Provide a fallback name if text is empty
                        if not text:
                            text = href.split("/")[-1] if href else "documento_adjunto"
                        download_candidates.append((el, text))
                
                # EXTRACT MAIN RESOLUTION FROM IFRAME
                # The main document (like a Resolución) is often embedded in an iframe named "contenedorMensaje"
                # instead of being listed as a regular <a> link. We can extract its id_archivo from the src attribute
                # and generate a standard download link.
                try:
                    iframe_el = await frame.query_selector("#contenedorMensaje")
                    if iframe_el:
                        src = await iframe_el.get_attribute("src")
                        if src and "id_archivo" in src:
                            import urllib.parse
                            
                            # The src usually contains URL-encoded JSON in a "datos" parameter
                            decoded_src = urllib.parse.unquote(src)
                            id_match = re.search(r'"id_archivo"\s*:\s*"(\d+)"', decoded_src)
                            doc_match = re.search(r'"num_doc"\s*:\s*"([^"]+)"', decoded_src)
                            
                            if id_match:
                                id_archivo = id_match.group(1)
                                num_doc = doc_match.group(1) if doc_match else f"resolucion_{id_archivo}"
                                
                                # Reconstruct standard download URL
                                dl_url = f"/ol-ti-itvisornoti/visor/bajarArchivo/{id_archivo}/0/0/{ruc}"
                                
                                # Inject hidden link into the DOM so Playwright can click it
                                link_id = f"hidden-dl-{id_archivo}"
                                js_code = f"""() => {{
                                    if (!document.getElementById('{link_id}')) {{
                                        const a = document.createElement('a');
                                        a.href = '{dl_url}';
                                        a.id = '{link_id}';
                                        a.innerText = '{num_doc}';
                                        document.body.appendChild(a);
                                    }}
                                }}"""
                                await frame.evaluate(js_code)
                                
                                injected_link = await frame.query_selector(f"#{link_id}")
                                if injected_link:
                                    download_candidates.append((injected_link, num_doc))
                                    logger.info(f"Extracted main resolution from iframe: {num_doc} (id: {id_archivo})")
                except Exception as e:
                    logger.warning(f"Could not extract main resolution from iframe: {str(e)}")

                logger.info(f"Identified {len(download_candidates)} candidate download links.")
                
                downloaded_files = []
                doc_dir = f"/app/storage/documents/{ruc}"
                os.makedirs(doc_dir, exist_ok=True)
                
                for idx, (link, text) in enumerate(download_candidates):
                    logger.info(f"Attempting download for candidate {idx + 1}/{len(download_candidates)} ('{text}')...")
                    try:
                        # Short timeout to see if it triggers a download
                        async with page.expect_download(timeout=5000) as download_info:
                            await link.click()
                        download = await download_info.value
                        
                        temp_filename = download.suggested_filename
                        temp_file_path = os.path.join(doc_dir, f"temp_{temp_filename}")
                        await download.save_as(temp_file_path)
                        
                        # Validate the file content starts with %PDF- (checking the PDF magic number)
                        is_valid_pdf = False
                        header = b""
                        if os.path.exists(temp_file_path) and os.path.getsize(temp_file_path) > 0:
                            with open(temp_file_path, "rb") as f:
                                header = f.read(5)
                                if header.startswith(b"%PDF-"):
                                    is_valid_pdf = True
                                    
                        if is_valid_pdf:
                            final_filename = temp_filename
                            final_file_path = os.path.join(doc_dir, final_filename)
                            # Rename to final location
                            if os.path.exists(final_file_path):
                                os.remove(final_file_path)
                            os.rename(temp_file_path, final_file_path)
                            
                            # Calculate SHA256 hash
                            sha256_hash = hashlib.sha256()
                            with open(final_file_path, "rb") as f:
                                content = f.read()
                                sha256_hash.update(content)
                            file_hash = sha256_hash.hexdigest()
                            
                            downloaded_files.append({
                                "filename": final_filename,
                                "file_path": final_file_path,
                                "file_hash": file_hash,
                                "size": len(content)
                            })
                            logger.info(f"SUCCESS: Downloaded and verified PDF: {final_filename} ({len(content)} bytes)")
                        else:
                            logger.warning(f"Skipping file '{temp_filename}': Not a valid PDF (header: {header})")
                            if os.path.exists(temp_file_path):
                                os.remove(temp_file_path)
                                
                    except Exception as ex:
                        # Log warning but do not break the whole download phase
                        logger.warning(f"Candidate {idx + 1} did not trigger download or failed: {str(ex)}")
                        
                if not downloaded_files:
                    raise Exception("No valid PDF documents were downloaded from the notification.")
                
                logger.info(f"SUCCESS on attempt {attempt}: Downloaded {len(downloaded_files)} files.")
                return {
                    "success": True, 
                    "message": "File download successful",
                    "data": {
                        "asunto": asunto.strip(),
                        "files": downloaded_files
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

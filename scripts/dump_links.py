import asyncio
import logging
import sys
import os
import re

# Add path
sys.path.append("/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models import Company
from app.services.sunat import sunat_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dump-links")

# Setup database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@osorio-db:5432/osorio_platform")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

async def dump():
    db = SessionLocal()
    company = db.query(Company).filter(Company.ruc == "20541770039").first()
    if not company:
        print("Company not found")
        return
        
    ruc = company.ruc
    user = company.credentials.sol_user
    password_encrypted = company.credentials.sol_password_encrypted
    
    browser, page = await sunat_service._get_browser()
    try:
        from shared.security import security_manager
        password = security_manager.decrypt_password(password_encrypted)
        
        print("Navigating to login...")
        await page.goto(sunat_service.login_url, wait_until="networkidle", timeout=45000)
        await page.fill("#txtRuc", ruc)
        await page.fill("#txtUsuario", user)
        await page.fill("#txtContrasena", password)
        await page.click("#btnAceptar")
        
        print("Navigating to Mailbox...")
        try:
            async with page.expect_popup(timeout=20000) as popup_info:
                await page.click("text='Buzón Electrónico'", force=True)
            page = await popup_info.value
        except:
            pass
            
        print("Entering iframe...")
        await page.wait_for_load_state("networkidle", timeout=60000)
        await page.wait_for_selector("iframe[name='iframeApplication']", timeout=120000)
        frame = page.frame(name="iframeApplication")
        
        print("Opening Buzón Notificaciones...")
        await frame.wait_for_timeout(2000)
        await frame.click("text=Buzón Notificaciones")
        
        await frame.wait_for_selector("text=/ASUNTO:/i", timeout=45000)
        items = await frame.query_selector_all("text=/ASUNTO:/i")
        await items[0].click()
        await frame.wait_for_timeout(5000)
        
        # Dump frame content
        body_content = await frame.locator("body").inner_html()
        
        output_path = "/app/storage/iframe_dump.html"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(body_content)
        print(f"Iframe HTML dumped to {output_path}")
        
        # Search for document number in the HTML
        doc_num = "0230230900646"
        matches = [m.start() for m in re.finditer(doc_num, body_content)]
        print(f"Found {len(matches)} occurrences of '{doc_num}' in HTML.")
        for i, match_idx in enumerate(matches):
            surrounding = body_content[max(0, match_idx - 150):min(len(body_content), match_idx + 150)]
            print(f"\nMatch {i+1} at index {match_idx}:")
            print(f"--- CONTEXT ---\n{surrounding}\n--- END CONTEXT ---")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        await browser.close()
        db.close()

if __name__ == "__main__":
    asyncio.run(dump())

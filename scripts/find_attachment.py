import asyncio
import os
import sys
import re

sys.path.append("/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shared.models import Company
from app.services.sunat import sunat_service

async def dump():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@osorio-db:5432/osorio_platform")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    company = db.query(Company).filter(Company.ruc == "20541770039").first()
    
    browser, page = await sunat_service._get_browser()
    try:
        from shared.security import security_manager
        password = security_manager.decrypt_password(company.credentials.sol_password_encrypted)
        
        await page.goto(sunat_service.login_url, wait_until="networkidle", timeout=60000)
        await page.fill("#txtRuc", company.ruc)
        await page.fill("#txtUsuario", company.credentials.sol_user)
        await page.fill("#txtContrasena", password)
        await page.click("#btnAceptar")
        
        try:
            async with page.expect_popup(timeout=20000) as popup_info:
                await page.click("text='Buzón Electrónico'", force=True)
            page = await popup_info.value
        except:
            pass
            
        await page.wait_for_selector("iframe[name='iframeApplication']", timeout=120000)
        frame = page.frame(name="iframeApplication")
        
        await frame.wait_for_timeout(2000)
        await frame.click("text=Buzón Notificaciones")
        
        await frame.wait_for_selector("text=/ASUNTO:/i", timeout=60000)
        items = await frame.query_selector_all("text=/ASUNTO:/i")
        
        await items[0].click()
        await frame.wait_for_timeout(10000)
        
        html = await frame.locator("body").inner_html()
        
        doc_num = "0230230900646"
        matches = [m.start() for m in re.finditer(doc_num, html)]
        for i, match_idx in enumerate(matches):
            surrounding = html[max(0, match_idx - 300):min(len(html), match_idx + 300)]
            print(f"\nMatch {i+1}:\n{surrounding}\n")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await browser.close()
        db.close()

if __name__ == "__main__":
    asyncio.run(dump())

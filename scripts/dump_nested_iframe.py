import asyncio
import os
import sys

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
        
        print("Looking for nested iframe...")
        inner_frame = None
        for cf in frame.child_frames:
            if cf.name == "contenedorMensaje":
                inner_frame = cf
                break
                
        if inner_frame:
            print("Found nested iframe! Dumping its HTML...")
            html = await inner_frame.locator("body").inner_html()
            print(f"Nested iframe HTML length: {len(html)}")
            
            # Print links in nested iframe
            all_links = await inner_frame.query_selector_all("a, button, input[type='button']")
            print(f"Found {len(all_links)} clickable elements in nested iframe.")
            for i, link in enumerate(all_links):
                text = (await link.inner_text() or "").strip()
                if not text:
                    text = (await link.get_attribute("value") or "").strip()
                href = (await link.get_attribute("href") or "").strip()
                onclick = (await link.get_attribute("onclick") or "").strip()
                print(f"[{i}] TEXT: {repr(text)} | HREF: {repr(href)} | ONCLICK: {repr(onclick)}")
        else:
            print("Nested iframe NOT found!")
            
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        await browser.close()
        db.close()

if __name__ == "__main__":
    asyncio.run(dump())

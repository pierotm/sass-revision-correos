import os
import sys

# Ensure shared directory is in path
sys.path.append("/app")

from shared.services.email_service import email_service

def test_send():
    print("Starting email test script...")
    
    # Create two dummy pdf files to attach
    dummy_pdf_path1 = "/app/storage/test_dummy_1.pdf"
    dummy_pdf_path2 = "/app/storage/test_dummy_2.pdf"
    os.makedirs(os.path.dirname(dummy_pdf_path1), exist_ok=True)
    with open(dummy_pdf_path1, "w") as f:
        f.write("This is dummy PDF 1 for testing multi attachment.")
    with open(dummy_pdf_path2, "w") as f:
        f.write("This is dummy PDF 2 for testing multi attachment.")

    target_email = os.getenv("NOTIFICATION_EMAIL_TO", "pierotarazona822@gmail.com")
    print(f"Target Email: {target_email}")
    print(f"SMTP/Gmail Client Configured: {email_service.service is not None}")

    try:
        success = email_service.send_notification_email(
            to_email=target_email,
            company_name="APROFERROL S.A.",
            ruc="20541770039",
            file_paths=[dummy_pdf_path1, dummy_pdf_path2],
            original_subject="Constancia de Buzon Sunat Electrónico de Prueba - Múltiples Adjuntos"
        )
        if success:
            print("SUCCESS: Email sent successfully!")
        else:
            print("FAILED: email_service returned False")
    except Exception as e:
        print(f"ERROR: Email send failed: {str(e)}")

if __name__ == "__main__":
    test_send()

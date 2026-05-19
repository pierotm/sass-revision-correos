import os
import sys

# Ensure shared directory is in path
sys.path.append("/app")

from shared.services.email_service import email_service

def test_send():
    print("Starting email test script...")
    
    # Create a dummy pdf file to attach
    dummy_pdf_path = "/app/storage/test_dummy.pdf"
    os.makedirs(os.path.dirname(dummy_pdf_path), exist_ok=True)
    with open(dummy_pdf_path, "w") as f:
        f.write("This is a dummy PDF file content for testing.")

    target_email = os.getenv("NOTIFICATION_EMAIL_TO", "pierotarazona822@gmail.com")
    print(f"Target Email: {target_email}")
    print(f"SMTP/Gmail Client Configured: {email_service.service is not None}")

    try:
        success = email_service.send_notification_email(
            to_email=target_email,
            company_name="APROFERROL S.A.",
            ruc="20541770039",
            file_path=dummy_pdf_path,
            original_subject="Constancia de Buzon Sunat Electrónico de Prueba"
        )
        if success:
            print("SUCCESS: Email sent successfully!")
        else:
            print("FAILED: email_service returned False")
    except Exception as e:
        print(f"ERROR: Email send failed: {str(e)}")

if __name__ == "__main__":
    test_send()

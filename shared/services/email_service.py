import os
import base64
import logging
from email.message import EmailMessage
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import mimetypes

logger = logging.getLogger("email_service")

class EmailService:
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        self.token_uri = "https://oauth2.googleapis.com/token"

        if not all([self.client_id, self.client_secret, self.refresh_token]):
            logger.warning("Google OAuth credentials not fully configured. EmailService might fail.")
            self.service = None
        else:
            self.creds = Credentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri=self.token_uri,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            self.service = build('gmail', 'v1', credentials=self.creds)

    def send_notification_email(self, to_email: str, company_name: str, ruc: str, file_paths: list[str] | str, original_subject: str):
        if not self.service:
            raise Exception("EmailService is not properly configured with Google Credentials.")

        if isinstance(file_paths, str):
            file_paths = [file_paths]

        try:
            message = EmailMessage()
            message["To"] = to_email
            message["From"] = "me"  # 'me' uses the authenticated user's address
            message["Subject"] = f"Nueva Notificación SUNAT - {ruc} - {company_name}"

            # Body
            body_text = f"""
Se ha recibido una nueva notificación de SUNAT.

Empresa: {company_name}
RUC: {ruc}
Asunto Original: {original_subject}

Los documentos adjuntos contienen la constancia y archivos descargados.
"""
            # Check for missing files first to update body
            missing_files = []
            valid_paths = []
            for path in file_paths:
                if os.path.exists(path):
                    valid_paths.append(path)
                else:
                    logger.warning(f"Attachment file not found at {path}")
                    missing_files.append(os.path.basename(path))

            if missing_files:
                body_text += f"\n\n[ADVERTENCIA]: No se pudieron adjuntar los siguientes archivos porque no se encontraron en el disco: {', '.join(missing_files)}"

            message.set_content(body_text.strip())

            # Now add all valid attachments
            for path in valid_paths:
                mime_type, _ = mimetypes.guess_type(path)
                mime_type = mime_type or 'application/octet-stream'
                main_type, sub_type = mime_type.split('/', 1)

                with open(path, "rb") as f:
                    file_data = f.read()

                filename = os.path.basename(path)
                message.add_attachment(file_data, maintype=main_type, subtype=sub_type, filename=filename)

            # Encode the message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"raw": encoded_message}

            # Send the email
            send_message = self.service.users().messages().send(userId="me", body=create_message).execute()
            logger.info(f"Email sent successfully. Message Id: {send_message['id']}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise

email_service = EmailService()

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

    def send_notification_email(self, to_email: str, company_name: str, ruc: str, file_path: str, original_subject: str):
        if not self.service:
            raise Exception("EmailService is not properly configured with Google Credentials.")

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

El documento adjunto contiene la constancia descargada.
"""
            message.set_content(body_text.strip())

            # Attachment
            if os.path.exists(file_path):
                # Guess mimetype
                mime_type, _ = mimetypes.guess_type(file_path)
                mime_type = mime_type or 'application/octet-stream'
                main_type, sub_type = mime_type.split('/', 1)

                with open(file_path, "rb") as f:
                    file_data = f.read()

                filename = os.path.basename(file_path)
                message.add_attachment(file_data, maintype=main_type, subtype=sub_type, filename=filename)
            else:
                logger.warning(f"Attachment file not found at {file_path}")
                body_text += "\n\n[ADVERTENCIA]: No se pudo adjuntar el archivo PDF porque no se encontró en el disco."
                message.set_content(body_text.strip())

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

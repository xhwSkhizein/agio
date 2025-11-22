"""
Example email tools.
"""


class SendEmailTool:
    """Email sending tool."""

    name = "send_email"
    
    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = 587,
        username: str = None,
        password: str = None,
        from_address: str = "noreply@example.com"
    ):
        self.smtp_server = smtp_server or "smtp.example.com"
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_address = from_address
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str
    ) -> str:
        """
        Send an email.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            Email sending result
        """
        # This is a mock implementation
        return f"Email sent to {to}\nSubject: {subject}\n[Mock: Email would be sent via {self.smtp_server}]"
    
    def __call__(self, to: str, subject: str, body: str) -> str:
        """Make the tool callable."""
        return self.send_email(to, subject, body)

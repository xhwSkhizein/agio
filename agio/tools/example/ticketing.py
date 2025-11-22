"""
Example ticketing tools.
"""


class CreateTicketTool:
    """Ticket creation tool."""

    name = "create_ticket"
    
    def __init__(
        self,
        api_url: str = None,
        api_key: str = None,
        default_priority: str = "medium"
    ):
        self.api_url = api_url or "https://tickets.example.com/api"
        self.api_key = api_key
        self.default_priority = default_priority
    
    def create_ticket(
        self,
        title: str,
        description: str,
        priority: str = None
    ) -> str:
        """
        Create a support ticket.
        
        Args:
            title: Ticket title
            description: Ticket description
            priority: Ticket priority (low, medium, high)
            
        Returns:
            Ticket creation result
        """
        priority = priority or self.default_priority
        # This is a mock implementation
        return f"Created ticket: '{title}' with priority {priority}\nTicket ID: MOCK-12345"
    
    def __call__(self, title: str, description: str, priority: str = None) -> str:
        """Make the tool callable."""
        return self.create_ticket(title, description, priority)

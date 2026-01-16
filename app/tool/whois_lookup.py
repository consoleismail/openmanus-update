import asyncio
import httpx
from typing import Any, Dict, Optional
from pydantic import Field

from app.logger import logger
from app.tool.base import BaseTool, ToolResult

class WhoisLookup(BaseTool):
    """Tool for performing WHOIS/RDAP lookups on domains."""

    name: str = "whois_lookup"
    description: str = "Perform a WHOIS/RDAP lookup to get registration information for a domain. Use this to find the owner's email, registrar, and other contact details for a domain name."
    parameters: dict = {
        "type": "object",
        "properties": {
            "domain": {
                "type": "string",
                "description": "(required) The domain name to lookup (e.g., example.com).",
            }
        },
        "required": ["domain"],
    }

    async def execute(self, domain: str) -> ToolResult:
        """Execute the WHOIS/RDAP lookup."""
        logger.info(f"🔍 Performing WHOIS/RDAP lookup for {domain}...")
        
        # Clean domain name
        domain = domain.strip().lower()
        if domain.startswith("http://"):
            domain = domain[7:]
        if domain.startswith("https://"):
            domain = domain[8:]
        domain = domain.split("/")[0]

        try:
            # Use RDAP (Registration Data Access Protocol) which is HTTP-based
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to find the RDAP server for the TLD
                tld = domain.split(".")[-1]
                
                # We'll use a common RDAP bootstrap or a well-known server
                # For now, let's try a common one like rdap.org which redirects
                url = f"https://rdap.org/domain/{domain}"
                
                response = await client.get(url, follow_redirects=True)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract useful information
                    result_parts = [f"WHOIS/RDAP results for {domain}:"]
                    
                    # Registrar
                    entities = data.get("entities", [])
                    for entity in entities:
                        roles = entity.get("roles", [])
                        if "registrar" in roles:
                            vcard = entity.get("vcardArray", [])
                            if len(vcard) > 1:
                                for item in vcard[1]:
                                    if item[0] == "fn":
                                        result_parts.append(f"Registrar: {item[3]}")
                    
                    # Status
                    status = data.get("status", [])
                    if status:
                        result_parts.append(f"Status: {', '.join(status)}")
                    
                    # Events (Registration, Expiration)
                    events = data.get("events", [])
                    for event in events:
                        action = event.get("eventAction", "")
                        date = event.get("eventDate", "")
                        if action and date:
                            result_parts.append(f"{action.capitalize()}: {date}")

                    # Nameservers
                    nameservers = data.get("nameservers", [])
                    if nameservers:
                        ns_list = [ns.get("ldhName", "") for ns in nameservers]
                        result_parts.append(f"Nameservers: {', '.join(filter(None, ns_list))}")

                    return ToolResult(output="\n".join(result_parts))
                elif response.status_code == 404:
                    return ToolResult(error=f"Domain '{domain}' not found (HTTP 404). This might mean the domain is available for registration or the RDAP server doesn't have records for it. Try using 'web_search' to find information about this domain or its owner.")
                else:
                    return ToolResult(error=f"Failed to get RDAP data for {domain}: HTTP {response.status_code}. Consider trying 'web_search' as a fallback.")

        except Exception as e:
            logger.error(f"Error during WHOIS lookup for {domain}: {e}")
            return ToolResult(error=f"WHOIS lookup failed: {str(e)}. You might want to try 'web_search' to find information about this domain.")

if __name__ == "__main__":
    whois = WhoisLookup()
    result = asyncio.run(whois.execute("google.com"))
    print(result.output)

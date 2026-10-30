"""Serveur MCP qui expose la recherche de commerces."""
from mcp.server.fastmcp import FastMCP
from prospection import chercher_commerces

serveur = FastMCP("prospection")

@serveur.tool()
def rechercher_commerces(activite: str, zone: str, nombre: int = 5) -> list[dict]:
    """Recherche des commerces sur Google Maps au Sénégal par activité et zone."""
    return chercher_commerces(activite, zone, nombre)

if __name__ == "__main__":
    serveur.run()          # communique avec l'assistant par l'entrée/sortie standard

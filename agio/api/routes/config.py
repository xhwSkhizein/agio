from fastapi import APIRouter, HTTPException, Depends
from typing import Any, Dict
from pydantic import BaseModel
from agio.registry.manager import ConfigManager
from agio.api.dependencies import get_config_manager

router = APIRouter(prefix="/api/config", tags=["config"])

class ConfigUpdate(BaseModel):
    config: Dict[str, Any]
    validate_only: bool = False

@router.get("/", response_model=Dict[str, Any])
async def list_configs(manager: ConfigManager = Depends(get_config_manager)):
    """List all loaded configurations."""
    # ConfigManager doesn't have a direct "list all" method that returns configs, 
    # but registry does.
    return {
        name: config.model_dump() 
        for name, config in manager.registry.list_configs().items()
    }

@router.get("/{name}", response_model=Dict[str, Any])
async def get_config(name: str, manager: ConfigManager = Depends(get_config_manager)):
    """Get a specific configuration."""
    config = manager.registry.get_config(name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration '{name}' not found")
    return config.model_dump()

@router.put("/{name}")
async def update_config(name: str, update: ConfigUpdate, manager: ConfigManager = Depends(get_config_manager)):
    """Update a configuration."""
    
    # Ensure name matches
    if update.config.get("name") != name:
        raise HTTPException(status_code=400, detail="Configuration name mismatch")
        
    success, message = manager.update_component(
        component_name=name,
        new_config=update.config,
        validate_only=update.validate_only
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {"message": message}

@router.delete("/{name}")
async def delete_config(name: str, manager: ConfigManager = Depends(get_config_manager)):
    """Delete a configuration."""
    success, message = manager.delete_component(name)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
        
    return {"message": message}

@router.post("/reload")
async def reload_configs(manager: ConfigManager = Depends(get_config_manager)):
    """Reload all configurations from disk."""
    results = manager.reload_all()
    
    # Check if any failed
    failures = {k: v[1] for k, v in results.items() if not v[0]}
    
    if failures:
        return {
            "message": "Some configurations failed to reload",
            "failures": failures,
            "results": results
        }
        
    return {"message": "All configurations reloaded successfully", "results": results}

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yaml
import os
from pathlib import Path
import pandas as pd
import numpy as np
import json

# Initialize FastAPI app
app = FastAPI(title="Pacong API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Paths
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "pacong" / "config" / "settings.yaml"
REPORTS_DIR = BASE_DIR / "pacong" / "reports"

class URLConfig(BaseModel):
    urls: list[str]

@app.get("/api/config")
async def get_config():
    try:
        if not CONFIG_PATH.exists():
             return {"urls": []}
        
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            # Assuming the structure has a 'urls' or similar key, 
            # but based on generic structure, we might need to adapt.
            # For now, let's just return the raw config or a specific section.
            # If the user wants to configure URLs, we need to know where they are in settings.yaml.
            # Let's assume a simple structure for now or read the whole thing.
            return config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def update_config(config_data: dict):
    try:
        # This is a simplified update. In a real app, we'd want to merge or validate.
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/data")
async def get_data():
    """
    Get the latest commodity data.
    Scans the reports directory for the most recent CSV or JSON file.
    """
    try:
        if not REPORTS_DIR.exists():
            return {"data": []}
        
        # Find the latest Commodity CSV file
        # Prioritize commodity_data files
        files = list(REPORTS_DIR.glob("commodity_data*.csv"))
        
        if not files:
            # Fallback to any CSV if no commodity data found
            files = list(REPORTS_DIR.glob("*.csv"))
            
        if not files:
            return {"data": []}
        
        # Sort by filename (which contains timestamp) to get the latest
        latest_file = max(files, key=lambda f: f.name)
        
        # Read CSV
        df = pd.read_csv(latest_file)
        
        # Convert to list of dicts using to_json to handle NaN/Inf automatically
        data = json.loads(df.to_json(orient="records"))
        
        # Inject unit information
        unit_map = {
            "Gold": "oz", "黄金": "g",
            "Silver": "oz", "白银": "kg",
            "Copper": "ton", "铜": "ton",
            "Crude Oil": "barrel", "原油": "barrel", "WTI": "barrel", "Brent": "barrel",
            "Natural Gas": "MMBtu", "天然气": "MMBtu",
            "Corn": "bushel", "玉米": "bushel",
            "Soybeans": "bushel", "大豆": "bushel",
            "Wheat": "bushel", "小麦": "bushel"
        }
        
        for item in data:
            name = item.get("name", "")
            cname = item.get("chinese_name", "")
            # Try to find unit by name or chinese_name
            for key, unit in unit_map.items():
                if key in name or key in cname:
                    item["unit"] = unit
                    break
            if "unit" not in item:
                item["unit"] = ""

        return {"data": data, "source": latest_file.name}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)

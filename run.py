import uvicorn
import json
import os

if __name__ == "__main__":
    # Check if uvicorn_config.json exists and use its settings if possible
    config_path = "uvicorn_config.json"
    
    reload_dirs = ["hr_agent"]
    reload_excludes = ["logs", "*.log", "*.db", "*.pyc"]
    
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            reload_dirs = config.get("reload_dirs", reload_dirs)
            reload_excludes = config.get("reload_excludes", reload_excludes)

    print(f"Starting server watching dirs: {reload_dirs}")
    print(f"Excluding: {reload_excludes}")

    uvicorn.run(
        "hr_agent.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=reload_dirs,
        reload_excludes=reload_excludes
    )

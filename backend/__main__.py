import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run TravelBuddy API")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=args.port,
        reload=args.reload,
        loop="backend.app.core.runtime:loop_factory",
    )


if __name__ == "__main__":
    main()

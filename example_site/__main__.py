"""main script"""
import uvicorn

from backend.routing import APP


def main():
    """serve backend app"""
    uvicorn.run(APP, host='0.0.0.0', port=8000)


if __name__ == '__main__':
    main()

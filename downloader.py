"""Development entry point for the Multi-Downloader desktop application."""


def main() -> None:
    from multi_downloader.ui import main as run_application

    run_application()


if __name__ == "__main__":
    main()

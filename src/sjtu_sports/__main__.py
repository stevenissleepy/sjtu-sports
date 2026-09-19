"""Command-line entry point for the package."""

import sys


def main():
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(
            "用法: python -m sjtu_sports "
            "<login|list-venues|list-sports|reserve|capture|analyze> [参数]"
        )
        return

    command = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]

    if command == "login":
        from sjtu_sports.reserve.save_login import main as command_main
    elif command == "list-venues":
        from sjtu_sports.reserve.reserve import list_venues_main as command_main
    elif command == "list-sports":
        from sjtu_sports.reserve.reserve import list_sports_main as command_main
    elif command == "reserve":
        from sjtu_sports.reserve.reserve import main as command_main
    elif command == "capture":
        from sjtu_sports.analyze.capture import main as command_main
    elif command == "analyze":
        from sjtu_sports.analyze.analyze import main as command_main
    else:
        raise SystemExit(f"未知命令: {command}")

    command_main()


if __name__ == "__main__":
    main()

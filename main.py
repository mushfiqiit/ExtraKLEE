from analyze_missing_methods import find_missing_methods_with_usage


def main() -> None:
    missing_methods = find_missing_methods_with_usage()
    print(missing_methods)


if __name__ == "__main__":
    main()
from analyze_local_undefined_types import find_undefined_types
from global_type_definition_lookup import find_definitions_for_types


def main() -> None:
    print(find_definitions_for_types(find_undefined_types()))


if __name__ == "__main__":
    main()
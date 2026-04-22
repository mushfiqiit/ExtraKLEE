from analyze_missing_methods import find_all_calls_in_file
from global_method_lookup import resolve_method_classes


def main() -> None:
    usages = find_all_calls_in_file("array_ops.h")
 
    if not usages:
        print("No method calls found in array_ops.h.")
        return
 
    method_names = list({u["method_name"] for u in usages})
    class_map = resolve_method_classes(method_names)
 
    print(f"{'Method':<30} {'Class':<25} {'Line':>4}  Code")
    print("-" * 90)
    for entry in usages:
        name = entry["method_name"]
        cls  = class_map.get(name, "")
        print(
            f"  {name:<28} {cls or '(free function)':<25} {entry['usage_line']:>4}  {entry['usage_code']}"
        )


if __name__ == "__main__":
    main()
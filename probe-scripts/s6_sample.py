import json

SCRATCH = "/private/tmp/claude-501/-Users-midat/bf444fe9-d3fd-4c62-a3b3-f20f0009521f/scratchpad/hh"
d = json.load(open(f"{SCRATCH}/kz_python.json"))
items = d["items"]
pick = next((i for i in items if i.get("salary")), items[0])

KEEP = ["id", "name", "area", "salary", "salary_range", "employer", "schedule", "experience",
        "employment", "employment_form", "work_format", "published_at", "created_at",
        "snippet", "professional_roles", "alternate_url", "archived", "type", "premium"]
short = {k: pick.get(k) for k in KEEP if k in pick}
if isinstance(short.get("employer"), dict):
    short["employer"] = {k: v for k, v in short["employer"].items()
                        if k in ("id", "name", "accredited_it_employer", "trusted")}
print(json.dumps(short, ensure_ascii=False, indent=2))
print("\n--- полный список ключей элемента ---")
print(sorted(pick.keys()))
print("\n--- сколько из 100 элементов имеют непустой salary / salary_range ---")
print("salary:", sum(1 for i in items if i.get("salary")), "/", len(items))
print("salary_range:", sum(1 for i in items if i.get("salary_range")), "/", len(items))

import json


# load original data
with open("course_data/2026FA_instructors.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# transform (ONLY required fields)
custom_data = []
print(len(data))
count = 1 
for inst in data:
    custom_data.append({
        "id": count ,
        "name": inst.get("name", ""),
        "departments": inst.get("departments", []),
        "email": "",
        "office": "",
        "office_hours": ""
    })
    count += 1 


print(len(custom_data))
# save new file
with open("custom_instructors.json", "w", encoding="utf-8") as f:
    json.dump(custom_data, f, indent=2)

print("✅ Clean instructor file created")
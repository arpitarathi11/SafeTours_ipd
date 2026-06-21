import json

with open("hex_scores.json", "r") as f:
    data = json.load(f)

print(len(data))

target = "89608b0b61bffff"

found = [x for x in data if x["hex_id"] == target]

print(found)
import json
import pandas as pd

# Load the fixture
with open('core/fixtures/fixture.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Separate by model
users = pd.DataFrame([
    item['fields'] for item in data if item['model'] == 'core.user'
])

patients = pd.DataFrame([
    item['fields'] for item in data if item['model'] == 'core.patient'
])

print("Users loaded:", len(users))
print("Patients loaded:", len(patients))
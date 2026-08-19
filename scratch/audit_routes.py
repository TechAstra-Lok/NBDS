import sys, os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
app = create_app()
print('App created successfully:', app.name)

# List all registered routes
rules = sorted(app.url_map.iter_rules(), key=lambda r: r.rule)
for rule in rules:
    methods = ','.join(sorted(rule.methods - {'HEAD','OPTIONS'}))
    print(f'  {methods:20} {rule.rule}  -> {rule.endpoint}')
print(f'Total routes: {len(rules)}')

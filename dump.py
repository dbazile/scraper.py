import glob
import json

html = '''\
<html>
<head>
<meta charset="utf-8"/>
</head>
<body>
'''

for filename in glob.glob('*.json'):
    with open(filename) as fp:
        article = json.loads(fp.read())
    html += '\n<h1>{headline}</h1><code>{permalink}</code>{text}<hr/>'.format(**article)

html += '''
</body>
</html>
'''

with open('dump.html', 'w') as fp:
    fp.write(html)
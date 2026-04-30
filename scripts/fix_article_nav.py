import urllib.request, urllib.parse, ssl, json

HOST = '152.89.79.37'
PORT = 2083
USER = 'cadafdd1'
TOKEN = 'IQO8R2A9VRL2SMUUVSOP6KE3YO0F4V2D'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def cpanel_get(path):
    params = urllib.parse.urlencode({'dir': '/home/cadafdd1/public_html', 'file': path}).encode()
    req = urllib.request.Request(f'https://{HOST}:{PORT}/execute/Fileman/get_file_content', data=params, method='POST')
    req.add_header('Authorization', f'cpanel {USER}:{TOKEN}')
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode())['data']['content']

def cpanel_put(path, content):
    params = urllib.parse.urlencode({'dir': '/home/cadafdd1/public_html', 'file': path, 'content': content}).encode()
    req = urllib.request.Request(f'https://{HOST}:{PORT}/execute/Fileman/save_file_content', data=params, method='POST')
    req.add_header('Authorization', f'cpanel {USER}:{TOKEN}')
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return json.loads(r.read().decode()).get('status') == 1

html = cpanel_get('why-i-built-mneme.html')

# Fix anchor-only nav links to point back to homepage
fixes = [
    ('href="#start"',       'href="/#start"'),
    ('href="#about"',       'href="/#about"'),
    ('href="#what_we_do"',  'href="/#what_we_do"'),
    ('href="#works"',       'href="/#works"'),
    ('href="#contact"',     'href="/#contact"'),
    ('href="#"',            'href="/"'),          # logo/brand link
]

for old, new in fixes:
    html = html.replace(old, new)

ok = cpanel_put('why-i-built-mneme.html', html)
print('Fixed:', ok)

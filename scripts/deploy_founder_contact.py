import urllib.request, urllib.parse, ssl, json, os

HOST = '152.89.79.37'
PORT = '2083'
USER = 'cadafdd1'
TOKEN = 'IQO8R2A9VRL2SMUUVSOP6KE3YO0F4V2D'
AUTH = f'cpanel {USER}:{TOKEN}'

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_LOCAL  = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'site'))
BASE_REMOTE = '/home/cadafdd1/mnemehq.com'

FILES = [
    (os.path.join('founder', 'index.html'), 'founder'),
    (os.path.join('contact', 'index.html'), 'contact'),
]

def mkdir(remote_path):
    parent = remote_path.rsplit('/', 1)[0]
    name   = remote_path.rsplit('/', 1)[1]
    params = {
        'cpanel_jsonapi_module': 'Fileman',
        'cpanel_jsonapi_func':   'mkdir',
        'cpanel_jsonapi_version': '2',
        'path': parent,
        'name': name,
    }
    data = urllib.parse.urlencode(params).encode('utf-8')
    req  = urllib.request.Request(
        f'https://{HOST}:{PORT}/json-api/cpanel',
        data=data,
        headers={'Authorization': AUTH},
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read())

def upload(local_path, remote_subdir):
    with open(local_path, 'r', encoding='utf-8') as f:
        content = f.read()
    filename   = os.path.basename(local_path)
    remote_dir = BASE_REMOTE + ('/' + remote_subdir if remote_subdir else '')
    boundary   = '----MnemeDeploy2026'
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="dir"\r\n\r\n{remote_dir}\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="overwrite"\r\n\r\n1\r\n'
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="file-1"; filename="{filename}"\r\n'
        f'Content-Type: text/html\r\n\r\n{content}\r\n'
        f'--{boundary}--'
    ).encode('utf-8')
    req = urllib.request.Request(
        f'https://{HOST}:{PORT}/execute/Fileman/upload_files',
        data=body,
        headers={'Authorization': AUTH, 'Content-Type': f'multipart/form-data; boundary={boundary}'},
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        result = json.loads(r.read())
    ok = result.get('status') == 1 and result.get('data', {}).get('failed', 1) == 0
    return 'OK' if ok else f'FAIL: {result.get("errors", result)}'

# Create remote directories first
for _, subdir in FILES:
    res = mkdir(f'{BASE_REMOTE}/{subdir}')
    print(f'mkdir {subdir}: {res}')

# Upload files
for rel_path, subdir in FILES:
    local = os.path.normpath(os.path.join(BASE_LOCAL, rel_path))
    label = rel_path.replace(os.sep, '/')
    print(f'{label}: {upload(local, subdir)}')

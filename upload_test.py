import json
import urllib.request
import pathlib

base = 'http://localhost:8000'

signup_payload = {
    'tenant_name': 'Upload Test Tenant',
    'email': 'uploadtest+endpoint@example.com',
    'password': 'Password123!',
    'full_name': 'Upload Tester',
}
req = urllib.request.Request(
    f'{base}/auth/signup',
    data=json.dumps(signup_payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
)
with urllib.request.urlopen(req) as resp:
    signup = json.loads(resp.read().decode('utf-8'))
print('signup:', signup)
token = signup['access_token']
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {token}',
}
project_payload = {
    'name': 'Upload Test Project',
    'customer_name': 'Test Co',
    'currency': 'USD',
    'margin_percent': 10.0,
}
req = urllib.request.Request(
    f'{base}/projects',
    data=json.dumps(project_payload).encode('utf-8'),
    headers=headers,
)
with urllib.request.urlopen(req) as resp:
    project = json.loads(resp.read().decode('utf-8'))
print('project:', project)
project_id = project['id']
file_path = pathlib.Path('upload_test.txt')
file_path.write_text('Hello upload test', encoding='utf-8')

boundary = '---PythonFormBoundary7MA4YWxkTrZu0gW'
body = []
body.append(f'--{boundary}')
body.append('Content-Disposition: form-data; name="doc_type"')
body.append('')
body.append('RFP')
body.append(f'--{boundary}')
body.append('Content-Disposition: form-data; name="file"; filename="upload_test.txt"')
body.append('Content-Type: text/plain')
body.append('')
body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n' + file_path.read_bytes() + b'\r\n' + f'--{boundary}--\r\n'.encode('utf-8')
req = urllib.request.Request(
    f'{base}/projects/{project_id}/documents',
    data=body_bytes,
    headers={
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Authorization': f'Bearer {token}',
    },
)
with urllib.request.urlopen(req) as resp:
    upload = json.loads(resp.read().decode('utf-8'))
print('upload:', upload)
file_path.unlink()

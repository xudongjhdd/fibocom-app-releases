"""Publish immutable, verified staging chunks using a narrowly scoped Supabase user.
Never print tokens, passwords, release notes, or HTTP response bodies in public logs.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import tempfile
import urllib.error
import urllib.parse
import urllib.request

CHUNK = 8 * 1024 * 1024


class API:
    def __init__(self, base, headers):
        self.base, self.headers = base, headers

    def request(self, method, path, body=None):
        headers = dict(self.headers)
        if body is not None:
            body = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
            return json.loads(data) if data else None


class Staging(API):
    def __init__(self):
        super().__init__(os.environ['SUPABASE_URL'].rstrip('/'), {'apikey': os.environ['SUPABASE_ANON_KEY']})
        session = self.request('POST', '/auth/v1/token?grant_type=password', {
            'email': os.environ['APK_PUBLISHER_EMAIL'], 'password': os.environ['APK_PUBLISHER_PASSWORD']})
        if session['user'].get('app_metadata', {}).get('apk_publisher') is not True:
            raise ValueError('Publisher permission missing')
        self.headers['Authorization'] = 'Bearer ' + session['access_token']

    def rpc(self, name, body):
        return self.request('POST', '/rest/v1/rpc/' + name, body)

    def assemble(self, job, target):
        digest = hashlib.sha256()
        total = 0
        with open(target, 'wb') as output:
            for index, expected_hash in enumerate(job['chunk_hashes']):
                part_hash, part_size = hashlib.sha256(), 0
                path = f"/storage/v1/object/authenticated/apk-staging/{job['id']}/{index:06d}"
                request = urllib.request.Request(self.base + path, headers=self.headers)
                with urllib.request.urlopen(request, timeout=90) as response:
                    while data := response.read(1024 * 1024):
                        part_size += len(data)
                        if part_size > CHUNK:
                            raise ValueError('Oversized chunk')
                        output.write(data)
                        part_hash.update(data)
                        digest.update(data)
                if part_hash.hexdigest() != expected_hash or part_size != min(CHUNK, job['file_size'] - total):
                    raise ValueError('Chunk integrity check failed')
                total += part_size
        if total != job['file_size']:
            raise ValueError('APK size mismatch')
        with open(target, 'rb') as source:
            if source.read(4) != b'PK\x03\x04':
                raise ValueError('Invalid APK signature')
        return digest.hexdigest()

    def cleanup(self):
        jobs = self.request('GET', '/rest/v1/apk_uploads?status=in.(published,cancelled)&cleaned=eq.false&limit=100')
        for job in jobs:
            prefixes = [f"{job['id']}/{index:06d}" for index in range(len(job['chunk_hashes']))]
            self.request('DELETE', '/storage/v1/object/apk-staging', {'prefixes': prefixes})
            self.rpc('apk_mark_cleaned', {'p_id': job['id']})


class GitHub(API):
    def __init__(self):
        self.repo = os.environ['GITHUB_REPOSITORY']
        super().__init__('https://api.github.com', {
            'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
            'Accept': 'application/vnd.github+json', 'User-Agent': 'fibocom-apk-publisher',
            'X-GitHub-Api-Version': '2022-11-28'})
        self.root = '/repos/' + self.repo

    def upload(self, release, target, name):
        # Stream from disk; never hold the full APK in memory.
        parsed = urllib.parse.urlsplit(release['upload_url'].split('{')[0])
        if parsed.scheme != 'https' or parsed.hostname != 'uploads.github.com':
            raise ValueError('Unexpected upload host')
        conn = http.client.HTTPSConnection(parsed.hostname, timeout=600)
        try:
            conn.putrequest('POST', parsed.path + '?name=' + urllib.parse.quote(name, safe=''))
            for key, value in self.headers.items():
                conn.putheader(key, value)
            conn.putheader('Content-Type', 'application/vnd.android.package-archive')
            conn.putheader('Content-Length', str(Path(target).stat().st_size))
            conn.endheaders()
            with open(target, 'rb') as source:
                while data := source.read(1024 * 1024):
                    conn.send(data)
            response = conn.getresponse()
            payload = response.read()
            if response.status != 201:
                raise RuntimeError(f'GitHub upload HTTP {response.status}')
            return json.loads(payload)
        finally:
            conn.close()

    def publish(self, job, target, sha):
        tag = 'apk-' + job['channel'] + '-' + job['version']
        asset_name = tag + '.apk'
        marker = f"<!-- fibocom-upload:{job['id']} sha256:{sha} -->"
        # List includes drafts, allowing safe recovery after an interrupted attachment.
        release = None
        for page in range(1, 101):
            batch = self.request('GET', f'{self.root}/releases?per_page=100&page={page}')
            release = next((r for r in batch if r['tag_name'] == tag), None)
            if release or len(batch) < 100:
                break
        if release and marker not in (release.get('body') or ''):
            raise ValueError('Version already belongs to another release')
        if not release:
            release = self.request('POST', self.root + '/releases', {
                'tag_name': tag, 'target_commitish': 'main', 'name': job['version'],
                'body': job['description'] + '\n\n' + marker, 'draft': True,
                'prerelease': job['channel'] == 'beta'})
        assets = self.request('GET', f"{self.root}/releases/{release['id']}/assets?per_page=100")
        asset = next((a for a in assets if a['name'] == asset_name), None)
        if asset and (asset['state'] != 'uploaded' or asset['size'] != job['file_size'] or asset.get('digest') != 'sha256:' + sha):
            if not release['draft']:
                raise ValueError('Published asset integrity mismatch')
            self.request('DELETE', f"{self.root}/releases/assets/{asset['id']}")
            asset = None
        if not asset:
            if not release['draft']:
                raise ValueError('Published asset missing; manual review required')
            asset = self.upload(release, target, asset_name)
        if asset['state'] != 'uploaded' or asset['size'] != job['file_size'] or asset.get('digest') != 'sha256:' + sha:
            raise ValueError('GitHub asset integrity check failed')
        if release['draft']:
            self.request('PATCH', f"{self.root}/releases/{release['id']}", {'draft': False, 'prerelease': job['channel'] == 'beta', 'make_latest': 'false'})
        return release['id'], asset['browser_download_url']


def run():
    staging, github = Staging(), GitHub()
    # Bounded batch leaves ample headroom within the lease/workflow timeout.
    for _ in range(3):
        jobs = staging.rpc('apk_claim_upload', {})
        if not jobs:
            break
        job = jobs[0]
        result = {'p_id': job['id'], 'p_lease': job['lease_id'], 'p_release_id': None, 'p_download_url': None, 'p_sha256': None}
        try:
            with tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'app.apk'
                sha = staging.assemble(job, target)
                release_id, url = github.publish(job, target, sha)
            result.update(p_release_id=release_id, p_download_url=url, p_sha256=sha)
        except Exception as error:
            # Error bodies may contain credentials or untrusted text. Log only the class/status.
            code = getattr(error, 'code', None)
            result['p_error'] = f'Publication failed ({type(error).__name__}{" HTTP " + str(code) if code else ""}). Retry or contact the administrator.'
        staging.rpc('apk_finish_upload', result)
        print('Processed APK upload:', 'failed' if result.get('p_error') else 'published')
    staging.cleanup()


if __name__ == '__main__':
    run()

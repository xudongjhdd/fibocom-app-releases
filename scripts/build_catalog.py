"""Publish a credential-free APK catalog from this repository's GitHub Releases."""
import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone


def public_release(release):
    if release.get('draft') or not release.get('published_at'):
        return None
    keys = ('id', 'tag_name', 'name', 'body', 'prerelease', 'draft', 'published_at', 'html_url')
    row = {key: release.get(key) for key in keys}
    asset_keys = ('id', 'name', 'state', 'size', 'browser_download_url', 'digest')
    row['assets'] = [{key: asset.get(key) for key in asset_keys}
                     for asset in release.get('assets', [])
                     if asset.get('state') == 'uploaded' and asset.get('name', '').lower().endswith('.apk')]
    return row


def main():
    repository = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GITHUB_TOKEN']
    def request(path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request('https://api.github.com/repos/' + repository + path,
            data=body, method='PUT' if data is not None else 'GET', headers={
                'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json',
                'User-Agent': 'fibocom-release-catalog'})
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    releases = []
    for page in range(1, 1001):
        batch = request(f'/releases?per_page=100&page={page}')
        releases.extend(row for release in batch if (row := public_release(release)) is not None)
        if len(batch) < 100:
            break
    else:
        raise RuntimeError('Release pagination limit reached; catalog was not changed')
    releases.sort(key=lambda row: (row['published_at'], row['id']), reverse=True)
    current = request('/contents/releases.json?ref=main')
    old = json.loads(base64.b64decode(current['content']))
    if old.get('schemaVersion') == 1 and old.get('releases') == releases:
        print('Catalog already matches published releases.')
        return
    content = json.dumps({'schemaVersion': 1, 'updatedAt': datetime.now(timezone.utc).isoformat(),
                          'releases': releases}, ensure_ascii=False, indent=2) + '\n'
    request('/contents/releases.json', {'message': 'Update APK release catalog', 'sha': current['sha'],
        'branch': 'main', 'content': base64.b64encode(content.encode()).decode()})
    print(f'Published catalog for {len(releases)} releases.')


if __name__ == '__main__':
    main()

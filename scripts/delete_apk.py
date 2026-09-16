"""Delete an older managed APK release, preserving the latest release per channel."""
import os
import re
import urllib.error


def delete_release(request, root, release_id):
    if not re.fullmatch(r'[1-9][0-9]{0,15}', str(release_id)):
        raise ValueError('Invalid release ID')
    path = root + '/releases/' + str(release_id)
    try:
        target = request('GET', path)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return
        raise
    if not re.fullmatch(r'apk-(stable|beta)-.+', target.get('tag_name', '')) or not re.search(r'<!-- fibocom-upload:[a-f0-9-]{36} sha256:[a-f0-9]{64} -->', target.get('body') or ''):
        raise ValueError('Only website-managed APK releases may be deleted')
    releases = []
    for page in range(1, 1001):
        batch = request('GET', f'{root}/releases?per_page=100&page={page}')
        releases.extend(r for r in batch if not r.get('draft') and r.get('published_at') and any(a.get('state') == 'uploaded' and a.get('name', '').lower().endswith('.apk') and a.get('size', 0) > 0 for a in r.get('assets', [])))
        if len(batch) < 100:
            break
    else:
        raise ValueError('Cannot verify latest release')
    channel = bool(target.get('prerelease'))
    candidates = [r for r in releases if bool(r.get('prerelease')) == channel]
    if not candidates or max(candidates, key=lambda r:(r['published_at'], r['id']))['id'] == int(release_id):
        raise ValueError('Latest APK in this channel cannot be deleted')
    request('DELETE', path)


if __name__ == '__main__':
    from publish_apk import GitHub
    github = GitHub()
    delete_release(github.request, github.root, os.environ['DELETE_RELEASE_ID'])
    print('Older APK release deletion completed.')

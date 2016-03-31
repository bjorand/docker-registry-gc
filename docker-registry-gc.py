#!/usr/bin/env python

import os
import argparse
import logging
import requests
import humanize
import collections

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logging.getLogger('requests').setLevel(logging.WARN)

class DockerRegsitryGc:
    def __init__(self, host, port, path):
        self.path = path
        self.api_url = "http://%s:%d/v2/" % (host, port)
        self.all_blobs = {}
        self.linked_blobs = {}
        self._generate_blobs_map()
        self._request_registered_blobs()
        self.detached_blobs = {}

    def _blob_dir_path(self, blob):
        return "%s/docker/registry/v2/blobs/sha256/%s/%s" % (self.path, blob[0:2], blob)

    def _blob_data_path(self, blob):
        return "%s/data" % self._blob_dir_path(blob)

    def _generate_blobs_map(self):
        logging.info("Starting FS blobs parsing")
        for root, dirnames, filenames in os.walk("%s/docker/registry/v2/repositories/" % self.path):
            if root.find('_layers/sha256/') > 0:
                tokens = root.replace('docker/registry/v2/repositories/', '').split("/")
                sha = tokens[-1]
                name = tokens[-4]
                self.all_blobs[sha] = name
        logging.info("FS blobs parsed: %d blobs total" % len(self.all_blobs))

    def _request_blob_size(self, repository, blob):
        logging.debug("Requesting blob size for %s" % blob)
        url = "%s%s/blobs/sha256:%s" % (self.api_url, repository, blob)
        logging.debug("URL: %s" % url)
        res = requests.head(url)
        if res.status_code != 200:
            logging.warn("Unable to request blob size for %s: %s" % (blob, res))
            return None

        return int(res.headers['content-length'])

    def _request_registered_blobs(self):
        logging.info("Requesting linked blobs from API")
        for repo in requests.get("%s_catalog" % self.api_url).json()['repositories']:
            for tag in requests.get("%s%s/tags/list" % (self.api_url, repo)).json()['tags']:
                manifest = requests.get("%s%s/manifests/%s" % (self.api_url, repo, tag)).json()
                for blob in map(lambda x: x['blobSum'].split(':')[-1], manifest.get('fsLayers', {})):
                    self.linked_blobs[blob] = (repo, tag)
        logging.info("Linked blobs parsed: %d blobs total" % len(self.linked_blobs))

    def calculate_summary(self):
        class ImageStat:
            def __init__(self):
                self.total_size = 0
                self.linked_size = 0

            def add_blob(self, size, linked):
                self.total_size += size
                if linked:
                    self.linked_size += size

        counter_total = collections.defaultdict(lambda: ImageStat())
        linked_blobs = set(self.linked_blobs.keys())
        for (blob, name) in self.all_blobs.items():
            size = self._request_blob_size(name, blob)
            if size is not None and size > 0:
                if blob not in linked_blobs:
                    self.detached_blobs[blob] = name
                counter_total[name].add_blob(size, blob in linked_blobs)

        for (key, stat) in sorted(counter_total.items(), key=lambda (key, stat): stat.total_size, reverse=True):
            logging.info("[%s] : %s, linked: %s, detached: %s, size share: %0.2f%%" % (key,
                                                                    humanize.naturalsize(stat.total_size, gnu=True),
                                                                    humanize.naturalsize(stat.linked_size, gnu=True),
                                                                    humanize.naturalsize(stat.total_size - stat.linked_size,
                                                                                         gnu=True),
                                                                    100.0 * stat.linked_size / stat.total_size))

        logging.info("Total size: %s" % humanize.naturalsize(sum(map(lambda (key, stat): stat.total_size,
                                                                     counter_total.items())), gnu=True))

        logging.info("Total linked blobs size: %s" % humanize.naturalsize(sum(map(lambda (key, stat): stat.linked_size,
                                                                     counter_total.items())), gnu=True))

    def clean_detached_blobs(self, dry_run):
        logging.info("Running clean up, dry-run = %s" % dry_run)
        for (blob, name) in self.detached_blobs.items():
            logging.info("Removing blob %s from %s,"
                         " size: %s" % (blob, name,humanize.naturalsize(self._request_blob_size(name, blob))))
            if not dry_run:
                url = "%s%s/blobs/sha256:%s" % (self.api_url, name, blob)
                logging.info("Removing from API %s" % url)
                res = requests.delete(url)
                if res.status_code != 202:
                    logging.warn("Strange response from API %s" % res)
                logging.info("Removing blob from FS %s" % self._blob_dir_path(blob))
                os.remove(self._blob_data_path(blob))
                os.rmdir(self._blob_dir_path(blob))
                assert not os.path.exists(self._blob_dir_path(blob)), \
                    "Unable to delete path %s" % self._blob_dir_path(blob)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Docker registry gc script')
    parser.add_argument('--host', metavar='H', type=str, nargs='?',
                        help='docker registry host', default=os.environ.get('DOCKER_REGISTRY_HOST', 'registry'))
    parser.add_argument('--port', metavar='P', type=int, nargs='?',
                        help='docker registry port', default=os.environ.get('DOCKER_REGISTRY_PORT', '5000'))
    parser.add_argument('--path', metavar='V', type=str, nargs='?',
                        help='docker registry data dir', default=os.environ.get('DOCKER_REGISTRY_PATH', '/var/lib/registry'))
    parser.add_argument('--delete', metavar='D', type=str, nargs='?',
                        help='set to yes to delete detached blobs', default=os.environ.get('DOCKER_REGISTRY_DELETE', 'no'))

    args = parser.parse_args()
    gc = DockerRegsitryGc(args.host, args.port, args.path)
    gc.calculate_summary()
    gc.clean_detached_blobs(args.delete != 'yes')

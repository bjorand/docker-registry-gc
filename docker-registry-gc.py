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
        self.blobs = {}
        self._calculate()

    def _calculate(self):
        logging.debug("Starting blobs parsing")
        for root, dirnames, filenames in os.walk("%s/docker/registry/v2/repositories/" % self.path):
            if root.find('_layers/sha256/') > 0:
                tokens = root.replace('docker/registry/v2/repositories/', '').split("/")
                sha = tokens[-1]
                name = tokens[-4]
                self.blobs[sha] = name
        logging.info("Blobs parsed: %d blobs total" % len(self.blobs))

    def _request_blob_size(self, repository, blob):
        logging.debug("Requesting blob size for %s" % blob)
        url = "%s%s/blobs/sha256:%s" % (self.api_url, repository, blob)
        logging.debug("URL: %s" % url)
        res = requests.head(url)
        if res.status_code != 200:
            logging.warn("Unable to request blob size for %s: %s" % (blob, res))
            return None

        return int(res.headers['content-length'])

    def calculate_summary(self):
        counter = collections.defaultdict(lambda: [])
        for (blob, name) in self.blobs.items():
            size = self._request_blob_size(name, blob)
            if size is not None:
                counter[name].append(size)
        for (key, size) in sorted(map(lambda (key, sizes): (key, sum(sizes)), counter.items()),
                                  key=lambda (key, size): size, reverse=True):
            logging.info("[%s] : %s" % (key, humanize.naturalsize(size, gnu=True)))

        logging.info("Total size: %s" % humanize.naturalsize(sum(map(lambda (key, sizes): sum(sizes), counter.items())),
                                                      gnu=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Docker registry gc script')
    parser.add_argument('--host', metavar='H', type=str, nargs='?',
                        help='docker registry host', default=os.environ.get('DOCKER_REGISTRY_HOST', 'registry'))
    parser.add_argument('--port', metavar='P', type=int, nargs='?',
                        help='docker registry port', default=os.environ.get('DOCKER_REGISTRY_PORT', '5000'))
    parser.add_argument('--path', metavar='V', type=str, nargs='?',
                        help='docker registry data dir', default=os.environ.get('DOCKER_REGISTRY_PATH', '/var/lib/registry'))
    args = parser.parse_args()
    gc = DockerRegsitryGc(args.host, args.port, args.path)
    gc.calculate_summary()

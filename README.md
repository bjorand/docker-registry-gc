# docker-registry-gc

Docker registry GC aims to solve the problem with the registry running out of disk space. When pushing the image 
with the existing tag to the docker registry blobs from the old image remains stored in the registry. 
If you are using docker in a CI pipeline you may be running out of disk space. As for 2.3 release of docker registry 
there are no way to list the orphaned blobs and to purge it out of the file system. The tool provides the method to
purge orphaned blobs and reduce disk space.

**DANGER** The tool is provided AS IS, it is in development stage for now and it could crush your registry.

## How it works

* Scans the registry file system to list all blobs in the registry.
* Requests the catalog of images and tags registered in the registry.
* Calculates stats for orphaned blobs and prints it out.
* Removes te orphaned blobs from the registry

## Building the Docker Image

``
docker build -t docker-registry-gc .
``

## Running as a Docker Container

To run the tool you have to link the docker registry container and attach volumes from the container. The registry must be 
configured with the volume (as a host dir or volume container):

``
docker run --rm -p 5000:5000 -v /var/lib/registry -e REGISTRY_STORAGE_DELETE_ENABLED=true --name registry registry:2
``

The tool launched with the command:

``
docker run -it --rm --volumes-from registry
    --link registry:registry -e DOCKER_REGISTRY_DELETE=yes
    --name docker-registry-gc docker-registry-gc
``
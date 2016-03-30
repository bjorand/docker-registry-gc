FROM python:2.7

RUN pip install requests && pip install humanize

ADD docker-registry-gc.py /opt/

RUN chmod a+x /opt/docker-registry-gc.py

CMD /opt/docker-registry-gc.py
#CMD bash
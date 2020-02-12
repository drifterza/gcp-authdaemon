FROM docker.io/opendevorg/python-base

COPY authdaemon.py /

ENTRYPOINT ["/authdaemon.py"]
CMD ["/authdaemon/token"]

FROM debian:stretch

RUN mkdir -p /var/local/bin
COPY ./build/qps_worker /var/local/bin
ENTRYPOINT [ "/var/local/bin/qps_worker" ]

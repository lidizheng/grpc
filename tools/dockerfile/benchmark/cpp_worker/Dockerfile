FROM debian:stretch

# Install packages needed for gRPC and protobuf
RUN apt-get update && apt-get install -y \
      autoconf \
      automake \
      build-essential \
      curl \
      git \
      g++ \
      libtool \
      make \
      cmake \
      pkg-config \
      unzip && apt-get clean

#=================
# C++ dependencies
RUN apt-get update && apt-get -y install libgflags-dev libgtest-dev libc++-dev clang && apt-get clean

# Google Cloud platform API libraries
RUN apt-get update && apt-get install -y python-pip && apt-get clean
RUN pip install --upgrade google-api-python-client oauth2client

RUN mkdir /var/local/work

VOLUME ["/var/local/src", "/var/local/output"]

# COPY ./build.sh /var/local/work
CMD [ "/var/local/output/build.sh" ]

FROM pataquets/collectd-python-pip

RUN \
  apt-get update && \
  DEBIAN_FRONTEND=noninteractive \
    apt-get -y install libmysqlclient-dev \
  && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache mysqlclient

RUN \
  ln -vs /etc/collectd/conf-available/write-csv-stdout.conf \
    /etc/collectd/conf.d/ \
  && \
  nl \
    /etc/collectd/collectd.conf \
    /etc/collectd/conf.d/*

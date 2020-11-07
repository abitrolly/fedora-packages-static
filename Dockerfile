FROM fedora:latest

RUN dnf -y upgrade \
  && dnf -y install \
  nginx \
  uwsgi \
  uwsgi-plugin-python3 \
  supervisor \
  make \
  python3-requests \
  python3-jinja2 \
  npm \
  cronie \
  cronie-anacron \
  rsync

WORKDIR /usr/local/src/packages

RUN mkdir /srv/packages
ENV OUTPUT_DIR /srv/packages

RUN mkdir /etc/packages
ENV DB_DIR /etc/packages/repositories
ENV MAINTAINER_MAPPING /etc/packages/pagure_owner_alias.json
ENV SOLR_CORE packages
ENV SOLR_URL http://127.0.0.1:8983/

COPY . .
RUN chmod -R o+rx assets

RUN make setup-js \
  && make js

COPY container/nginx.conf /etc/nginx/nginx.conf
COPY container/update-packages.sh /etc/cron.weekly/
COPY container/supervisord.conf /etc/supervisord.conf

# TODO: Figure out how to use a read-write volume for
#  one container that manages static files
#  and just serve from the rest with read-only mounts
VOLUME /srv/packages
EXPOSE 80

ENTRYPOINT [ "./container/entrypoint.sh" ]

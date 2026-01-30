# smtp-graph-relay
A primitive SMTP server that will relay requests to the MS Graph mail API

```
mailuser="someusername"
useradd -r -m "$mailuser"
docker run \
  -e CLIENT_ID="" \
  -e SECRET_ID="" \
  -e TENANT_ID="" \
  -e SENDER="a@b.co" \
  -e RECIPIENT="c@d.co" \
  -e CERT_FILE="/path/to/cert" \
  -e KEY_FILE="/path/to/key" \
  -p 8587:8587 \
  -v /local/path/to/cert:/path/to/cert:ro
  -v /local/path/to/key:/path/to/key:ro
  -u "$(id -u $mailuser):$(id -g $mailuser)"
  smtp-graph-relay:latest
```
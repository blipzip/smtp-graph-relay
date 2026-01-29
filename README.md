# smtp-graph-relay
A primitive SMTP server that will relay requests to the MS Graph mail API

```
docker build -t smtp-graph-relay .
docker run \
  -e CLIENT_ID="" \
  -e SECRET_ID="" \
  -e TENANT_ID="" \
  -e SENDER="a@b.co" \
  -e RECIPIENT="c@d.co" \
  -p 2525:2525 \
  smtp-graph-relay:latest
```